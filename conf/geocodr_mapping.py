# -:- encoding: utf-8 -:-
from __future__ import unicode_literals
import re

from datetime import datetime

from geocodr import proj
from geocodr.search import (
    Collection as BaseCollection,
    GermanNGramField as NGramField,
    SimpleField,
    PrefixField,
    Only,
    PatternReplace,
)

gemarkung_prefix = '13' # Prefix added to 4-digit Gemarkungsnummern (13=Mecklenburg-Vorpommern)


class Collection(BaseCollection):
    """
    Base class for all Collections. Sets project dependent options like projection, etc.
    """
    # all geometries are in EPSG:25833
    src_proj = proj.epsg(25833)

    class_title_attrib = 'suchklasse'
    collection_title_attrib = 'objektgruppe'
    distance_attrib = 'entfernung'

    geometry_field = 'geometrie'

    # retrieve all fields from Solr, including score and full geometry as WKT
    field_list = '*,score,geometrie:[geo f=geometrie w=WKT]'


def ReplaceStrasse(field):
    """
    Wrap field with pattern replace. We replace all forms of wrong apostrophes
    with correct apostrophes as well as str, stra, ..., straße suffix
    with str (all case-insensitive). This is already implemented in the Solr schema,
    but it does not work with our NGramField, as we build the grams on our own.
    A boost must be applied to the field, not this wrapped result.
    """
    return PatternReplace('′', '’', PatternReplace('´', '’', PatternReplace('`', '’', PatternReplace('‘', '’', PatternReplace('\'', '’', PatternReplace(
        r'(?i)str(a((ß|ss?)e?)?)?\b', 'str.',
        PatternReplace(r'\Bstr.', ' str.', field)
    ))))))


class Strassen(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'strassen'
    title = 'Straße'
    fields = ('strasse_name', 'gemeinde_name', 'gemeindeteil_name')
    qfields = (
        ReplaceStrasse(NGramField('strasse_name_ngram') ^ 1.6),
        NGramField('gemeinde_name_ngram') ^ 1.2,
        SimpleField('strasse_name') ^ 3.2,
        SimpleField('gemeinde_name') ^ 2.2,
    )
    sort = 'score DESC, gemeinde_name ASC, strasse_name ASC'
    sort_fields = ('gemeinde_name', 'strasse_name')
    collection_rank = 3

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        if prop['gemeindeteil_name']:
            parts.append(prop['gemeindeteil_name'])
        parts.append(prop['strasse_name'])
        return ', '.join(parts)

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            not doc['gemeinde_ist_stadt'],
            -doc['gemeinde_flaeche'],
            # longest first
            -doc['strasse_laenge'],
            doc['gemeinde_name'],
            doc['strasse_name'],
        )

class Adressen(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'adressen'
    title = 'Adresse'
    fields = ('strasse_name', 'gemeindeteil_name', 'gemeinde_name',
              'postleitzahl')
    # results with identical fields (except for different hausnummer)
    # will get the same score
    align_score_fields = ('strasse_name', 'gemeindeteil_name', 'gemeinde_name',
                          'postleitzahl')
    qfields = (
        SimpleField('strasse_name') ^ 1.2,
        ReplaceStrasse(NGramField('strasse_name_ngram') ^ 0.8),
        SimpleField('gemeinde_name') ^ 0.6,
        NGramField('gemeinde_name_ngram') ^ 0.4,
        SimpleField('gemeindeteil_name') ^ 0.8,
        NGramField('gemeindeteil_name_ngram') ^ 0.6,
        # search for housenumbers only in hausnummer
        Only('^\d{1,3}[a-zA-Z]{,2}$', PrefixField('hausnummer', 1)),
        # search for zip codes only in postleitzahl
        Only('^\d{3,5}$', PrefixField('postleitzahl')),
    )
    sort = 'score DESC, gemeinde_ist_stadt DESC, gemeinde_name ASC, strasse_name ASC, ' \
        'strasse_schluessel ASC, hausnummer_int ASC, hausnummer ASC'

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        if prop['gemeindeteil_name']:
            parts.append(prop['gemeindeteil_name'])
        parts.append(prop['strasse_name'] + ' ' + prop['hausnummer'] +
                     (prop['hausnummer_zusatz'] or ''))
        return ', '.join(parts)

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            not doc['gemeinde_ist_stadt'],
            -doc['gemeinde_flaeche'],
            doc['strasse_name'],
            doc['strasse_schluessel'],
            # sort by integer value only
            int(re.match(r'\d+', doc['hausnummer']).group(0)),
            doc['hausnummer'],
        )

    def to_features(self, docs, **kw):
        # Iterate through all docs and align scores.
        #
        # SolrCloud can return different scores for identical search field.
        # This is due to different document counts on different shards (even
        # with ExactStatsCache). We iterate through all docs and check for
        # identical keys (align_score_fields) and a similar score.
        prev_key = None
        prev_score = 0

        for doc in docs:
            key = tuple(doc.get(f) for f in self.align_score_fields)
            if key == prev_key and prev_score/doc['score'] < 1.01:
                doc['score'] = prev_score

            prev_key = key
            prev_score = doc['score']

        return Collection.to_features(self, docs, **kw)


class Gemeinden(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'gemeinden'
    title = 'Gemeinde'
    fields = ('gemeinde_name',)
    qfields = (
        NGramField('gemeinde_name_ngram') ^ 2.4,
        # higher then gemeindeteil_name in GemeindeTeile
        SimpleField('gemeinde_name') ^ 4.4,
    )
    sort = 'score DESC, gemeinde_name ASC'
    sort_fields = ('gemeinde_name', )
    collection_rank = 1

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            # stadt first
            not doc['gemeinde_ist_stadt'],
            # largest first
            -doc['gemeinde_flaeche'],
            doc['gemeinde_name'],
        )

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        return ', '.join(parts)


class GemeindeTeile(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'gemeindeteile'
    title = 'Gemeindeteil'
    fields = ('gemeinde_name', 'gemeindeteil_name')
    qfields = (
        NGramField('gemeindeteil_name_ngram') ^ 1.3,
        SimpleField('gemeindeteil_name') ^ 3.3,
        NGramField('gemeinde_name_ngram') ^ 1.3,
        SimpleField('gemeinde_name') ^ 2.3,
    )
    sort = 'score DESC, gemeinde_name ASC, gemeindeteil_name ASC'
    sort_fields = ('gemeinde_name', 'gemeindeteil_name')
    collection_rank = 2

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        if prop['gemeindeteil_name']:
            parts.append(prop['gemeindeteil_name'])
        return ', '.join(parts)

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            -doc['gemeindeteil_flaeche'],
            doc['gemeinde_name'],
        )

class StrassenHro(Collection):
    class_ = 'address_hro'
    class_title = 'Adresse HRO'
    name = 'strassen_hro'
    title = 'Straße HRO'
    fields = ('strasse_name', 'gemeinde_name', 'gemeindeteil_name')
    qfields = (
        ReplaceStrasse(NGramField('strasse_name_ngram') ^ 1.6),
        NGramField('gemeinde_name_ngram') ^ 1.2,
        SimpleField('strasse_name') ^ 3.2,
        SimpleField('gemeinde_name') ^ 2.2,
    )
    sort = 'score DESC, gemeinde_name ASC, strasse_name ASC'
    sort_fields = ('gemeinde_name', 'strasse_name')
    collection_rank = 3

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeindeteil_name'])
        parts.append(prop['strasse_name'])
        return ', '.join(parts)

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            # longest first
            -doc['strasse_laenge'],
            doc['gemeinde_name'],
            doc['strasse_name'],
        )


class AdressenHro(Collection):
    class_ = 'address_hro'
    class_title = 'Adresse HRO'
    name = 'adressen_hro'
    title = 'Adresse HRO'
    fields = ('strasse_name', 'gemeindeteil_name', 'gemeinde_name',
              'postleitzahl')
    # results with identical fields (except for different hausnummer)
    # will get the same score
    align_score_fields = ('strasse_name', 'gemeindeteil_name', 'gemeinde_name',
                          'postleitzahl')
    qfields = (
        SimpleField('strasse_name') ^ 1.2,
        ReplaceStrasse(NGramField('strasse_name_ngram') ^ 0.8),
        SimpleField('gemeinde_name') ^ 0.6,
        NGramField('gemeinde_name_ngram') ^ 0.4,
        SimpleField('gemeindeteil_name') ^ 0.8,
        NGramField('gemeindeteil_name_ngram') ^ 0.6,
        # search for housenumbers only in hausnummer
        Only('^\d{1,3}[a-zA-Z]{,2}$', PrefixField('hausnummer', 1)),
        # search for zip codes only in postleitzahl
        Only('^\d{3,5}$', PrefixField('postleitzahl')),
    )
    sort = 'score DESC, gemeinde_name ASC, strasse_name ASC, ' \
        'strasse_schluessel ASC, hausnummer_int ASC, hausnummer ASC'

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeindeteil_name'])
        parts.append(prop['strasse_name'] + ' ' + prop['hausnummer'] + (prop['hausnummer_zusatz'] or ''))
        if prop['gueltigkeit_bis']:
            parts[-1] += ' – historisch seit ' + datetime.strptime(prop['gueltigkeit_bis'], '%Y-%m-%d').strftime('%d.%m.%Y')
        return ', '.join(parts)

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            doc['strasse_name'],
            doc['strasse_schluessel'],
            # sort by integer value only
            int(re.match(r'\d+', doc['hausnummer']).group(0)),
            doc['hausnummer'],
        )

    def to_features(self, docs, **kw):
        # Iterate through all docs and align scores.
        #
        # SolrCloud can return different scores for identical search field.
        # This is due to different document counts on different shards (even
        # with ExactStatsCache). We iterate through all docs and check for
        # identical keys (align_score_fields) and a similar score.
        prev_key = None
        prev_score = 0

        for doc in docs:
            key = tuple(doc.get(f) for f in self.align_score_fields)
            if key == prev_key and prev_score/doc['score'] < 1.01:
                doc['score'] = prev_score

            prev_key = key
            prev_score = doc['score']

        return Collection.to_features(self, docs, **kw)


class GemeindeTeileHro(Collection):
    class_ = 'address_hro'
    class_title = 'Adresse HRO'
    name = 'gemeindeteile_hro'
    title = 'Gemeindeteil HRO'
    fields = ('gemeinde_name', 'gemeindeteil_name')
    qfields = (
        NGramField('gemeindeteil_name_ngram') ^ 1.3,
        SimpleField('gemeindeteil_name') ^ 3.3,
        NGramField('gemeinde_name_ngram') ^ 1.3,
        SimpleField('gemeinde_name') ^ 2.3,
    )
    sort = 'score DESC, gemeinde_name ASC, gemeindeteil_name ASC'
    sort_fields = ('gemeinde_name', 'gemeindeteil_name')
    collection_rank = 2

    def to_title(self, prop):
        return prop['gemeindeteil_name']

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            -doc['gemeindeteil_flaeche'],
            doc['gemeinde_name'],
        )


class Gemarkungen(Collection):
    class_ = 'parcel'
    class_title = 'Flurstück'
    name = 'gemarkungen'
    title = 'Gemarkung'
    fields = ('gemeinde_name', 'gemarkung_name')
    qfields = (
        NGramField('gemarkung_name_ngram') ^ 1.5,
        SimpleField('gemarkung_name') ^ 3.5,
        NGramField('gemeinde_name_ngram') ^ 1.5,
        SimpleField('gemeinde_name') ^ 2.5,
        SimpleField('gemarkung_schluessel') ^ 4.5,
    )
    sort = 'score DESC, gemeinde_name ASC, gemarkung_name ASC'
    sort_fields = ('gemeinde_name', 'gemarkung_name')
    collection_rank = 1

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        parts.append(prop['gemarkung_name'] + ' (' + prop['gemarkung_schluessel'][2:] + ')')
        return ', '.join(parts)

    def query(self, query):
        if re.match(r'^\d{4,4}$', query):
            query = gemarkung_prefix + query

        return Collection.query(self, query)


class Fluren(Collection):
    class_ = 'parcel'
    class_title = 'Flurstück'
    name = 'fluren'
    title = 'Flur'
    fields = ('gemeinde_name', 'gemarkung_name', 'flur')
    qfields = (
        NGramField('gemarkung_name_ngram'),
        SimpleField('gemarkung_name') ^ 3.0,
        NGramField('gemeinde_name_ngram'),
        SimpleField('gemeinde_name') ^ 2.0,
    )
    sort = 'score DESC, gemeinde_name ASC, gemarkung_name ASC, flur ASC'
    sort_fields = ('gemeinde_name', 'gemarkung_name', 'flur')
    collection_rank = 2

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        parts.append(prop['gemarkung_name'] + ' (' + prop['gemarkung_schluessel'][2:] + ')')
        parts.append('Flur ' + str(int(prop['flur'], 10)))
        return ', '.join(parts)

    def query(self, query):
        """
        Manually build Solr query for parcel identifiers (Flurstückkennzeichen).
        parse_flst splits different formats of the identifiers into their
        parts, from left to right. Only query if the identifier contains
        flurstuecksnummer and (optionaly) flur.
        """
        from geocodr.lib.flst import parse_flst
        flst = parse_flst(query, gemarkung_prefix=gemarkung_prefix)
        if not flst:
            return

        if flst.zaehler or flst.nenner:
            return

        qparts = []
        if flst.gemarkung_name:
            qparts.append(Collection.query(self, flst.gemarkung_name))
        else:
            qparts.append('gemarkung_schluessel:' + flst.gemarkung)

        if flst.flur:
            qparts.append('flur:' + flst.flur)

        return '{}'.format(' AND '.join(qparts))


class Flurstuecke(Collection):
    class_ = 'parcel'
    class_title = 'Flurstück'
    name = 'flurstuecke'
    title = 'Flurstück'
    fields = ('gemeinde_name', 'gemarkung_name', 'flurstueckskennzeichen')
    qfields = (
        NGramField('gemarkung_name_ngram'),
        SimpleField('gemarkung_name') ^ 3.0,
        NGramField('gemeinde_name_ngram'),
        SimpleField('gemeinde_name') ^ 2.0,
    )
    sort = 'score DESC, gemeinde_name ASC, gemarkung_name ASC, ' \
        'flurstuecksnummer ASC'
    sort_fields = ('flurstueckskennzeichen', )
    collection_rank = 3
    min_query_length = 2

    def to_features(self, docs, **kw):
        # Iterate through all docs and align scores.
        #
        # SolrCloud can return different scores for identical search field.
        # This is due to different document counts on different shards (even
        # with ExactStatsCache). We iterate through all docs and check for
        # a similar score.
        prev_score = 0

        for doc in docs:
            if prev_score and prev_score/doc['score'] < 1.1:
                doc['score'] = prev_score

            prev_score = doc['score']

        return Collection.to_features(self, docs, **kw)

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts.append(prop['gemeinde_name_suchzusatz'])
        parts.append(prop['gemarkung_name'] + ' (' + prop['gemarkung_schluessel'][2:] + ')')
        parts.append('Flur ' + str(int(prop['flur'], 10)))
        parts.append(str(int(prop['zaehler'], 10)))
        if prop['nenner'] != '0000':
            parts[-1] += '/' + str(int(prop['nenner'], 10))
        return ', '.join(parts)

    def query(self, query):
        """
        Manually build Solr query for parcel identifiers (Flurstückkennzeichen).
        parse_flst splits different formats of the identifiers into their
        parts, from left to right.
        """
        from geocodr.lib.flst import parse_flst
        flst = parse_flst(query, gemarkung_prefix=gemarkung_prefix)
        if not flst:
            return

        # Short form always contains zaehler, but no flur.
        is_short_form = flst.zaehler and not flst.flur

        # If we don't have a name, then we combine all parts to a single search prefix
        # string. The parts are always from left to right in the long-form (e.g. if we have
        # zaehler, we also have flur).
        if not flst.gemarkung_name and not is_short_form:
            return 'flurstuecksnummer:' + flst.gemarkung + flst.flur \
                + flst.zaehler + flst.nenner + '*'

        qparts = []

        if flst.gemarkung_name:
            qparts.append(Collection.query(self, flst.gemarkung_name))
        elif flst.gemarkung:
            qparts.append('flurstuecksnummer:' + flst.gemarkung + '*')

        if flst.flur:
            qparts.append('flur:' + flst.flur)
        if flst.nenner:
            qparts.append('nenner:' + flst.nenner)
        if flst.zaehler:
            qparts.append('zaehler:' + flst.zaehler)

        return '{}'.format(' AND '.join(qparts))


class GemarkungenHro(Collection):
    class_ = 'parcel_hro'
    class_title = 'Flurstück HRO'
    name = 'gemarkungen_hro'
    title = 'Gemarkung HRO'
    fields = ('gemeinde_name', 'gemarkung_name')
    qfields = (
        NGramField('gemarkung_name_ngram') ^ 1.5,
        SimpleField('gemarkung_name') ^ 3.5,
        NGramField('gemeinde_name_ngram') ^ 1.5,
        SimpleField('gemeinde_name') ^ 2.5,
        SimpleField('gemarkung_schluessel') ^ 4.5,
    )
    sort = 'score DESC, gemeinde_name ASC, gemarkung_name ASC'
    sort_fields = ('gemeinde_name', 'gemarkung_name')
    collection_rank = 1

    def to_title(self, prop):
        return prop['gemarkung_name'] + ' (' + prop['gemarkung_schluessel'][2:] + ')'

    def query(self, query):
        if re.match(r'^\d{4,4}$', query):
            query = gemarkung_prefix + query

        return Collection.query(self, query)


class FlurenHro(Collection):
    class_ = 'parcel_hro'
    class_title = 'Flurstück HRO'
    name = 'fluren_hro'
    title = 'Flur HRO'
    fields = ('gemeinde_name', 'gemarkung_name', 'flur')
    qfields = (
        NGramField('gemarkung_name_ngram'),
        SimpleField('gemarkung_name') ^ 3.0,
        NGramField('gemeinde_name_ngram'),
        SimpleField('gemeinde_name') ^ 2.0,
    )
    sort = 'score DESC, gemeinde_name ASC, gemarkung_name ASC, flur ASC'
    sort_fields = ('gemeinde_name', 'gemarkung_name', 'flur')
    collection_rank = 2

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemarkung_name'] + ' (' + prop['gemarkung_schluessel'][2:] + ')')
        parts.append('Flur ' + str(int(prop['flur'], 10)))
        return ', '.join(parts)

    def query(self, query):
        """
        Manually build Solr query for parcel identifiers (Flurstückkennzeichen).
        parse_flst splits different formats of the identifiers into their
        parts, from left to right. Only query if the identifier contains
        flurstuecksnummer and (optionaly) flur.
        """
        from geocodr.lib.flst import parse_flst
        flst = parse_flst(query, gemarkung_prefix=gemarkung_prefix)
        if not flst:
            return

        if flst.zaehler or flst.nenner:
            return

        qparts = []
        if flst.gemarkung_name:
            qparts.append(Collection.query(self, flst.gemarkung_name))
        else:
            qparts.append('gemarkung_schluessel:' + flst.gemarkung)

        if flst.flur:
            qparts.append('flur:' + flst.flur)

        return '{}'.format(' AND '.join(qparts))


class FlurstueckeHro(Collection):
    class_ = 'parcel_hro'
    class_title = 'Flurstück HRO'
    name = 'flurstuecke_hro'
    title = 'Flurstück HRO'
    fields = ('gemeinde_name', 'gemarkung_name', 'flurstueckskennzeichen')
    qfields = (
        NGramField('gemarkung_name_ngram'),
        SimpleField('gemarkung_name') ^ 3.0,
        NGramField('gemeinde_name_ngram'),
        SimpleField('gemeinde_name') ^ 2.0,
    )
    sort = 'score DESC, gemeinde_name ASC, gemarkung_name ASC, ' \
        'flurstuecksnummer ASC'
    sort_fields = ('flurstueckskennzeichen', )
    collection_rank = 3
    min_query_length = 2

    def to_features(self, docs, **kw):
        # Iterate through all docs and align scores.
        #
        # SolrCloud can return different scores for identical search field.
        # This is due to different document counts on different shards (even
        # with ExactStatsCache). We iterate through all docs and check for
        # a similar score.
        prev_score = 0

        for doc in docs:
            if prev_score and prev_score/doc['score'] < 1.1:
                doc['score'] = prev_score

            prev_score = doc['score']

        return Collection.to_features(self, docs, **kw)

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemarkung_name'] + ' (' + prop['gemarkung_schluessel'][2:] + ')')
        parts.append('Flur ' + str(int(prop['flur'], 10)))
        parts.append(str(int(prop['zaehler'], 10)))
        if prop['nenner'] != '0000':
            parts[-1] += '/' + str(int(prop['nenner'], 10))
        if prop['historisch_seit']:
            parts[-1] += ' – historisch seit ' + datetime.strptime(prop['historisch_seit'], '%Y-%m-%d').strftime('%d.%m.%Y')
        return ', '.join(parts)

    def query(self, query):
        """
        Manually build Solr query for parcel identifiers (Flurstückkennzeichen).
        parse_flst splits different formats of the identifiers into their
        parts, from left to right.
        """
        from geocodr.lib.flst import parse_flst
        flst = parse_flst(query, gemarkung_prefix=gemarkung_prefix)
        if not flst:
            return

        # Short form always contains zaehler, but no flur.
        is_short_form = flst.zaehler and not flst.flur

        # If we don't have a name, then we combine all parts to a single search prefix
        # string. The parts are always from left to right in the long-form (e.g. if we have
        # zaehler, we also have flur).
        if not flst.gemarkung_name and not is_short_form:
            return 'flurstuecksnummer:' + flst.gemarkung + flst.flur \
                + flst.zaehler + flst.nenner + '*'

        qparts = []

        if flst.gemarkung_name:
            qparts.append(Collection.query(self, flst.gemarkung_name))
        elif flst.gemarkung:
            qparts.append('flurstuecksnummer:' + flst.gemarkung + '*')

        if flst.flur:
            qparts.append('flur:' + flst.flur)
        if flst.nenner:
            qparts.append('nenner:' + flst.nenner)
        if flst.zaehler:
            qparts.append('zaehler:' + flst.zaehler)

        return '{}'.format(' AND '.join(qparts))


class Schulen(Collection):
    class_ = 'school'
    class_title = 'Schule'
    name = 'schulen'
    title = 'Schule'
    fields = ('bezeichnung', 'postleitzahl', 'strasse_name', 'art',
              'hausnummer', 'gemeinde_name', 'gemeindeteil_name')
    qfields = (
        SimpleField('bezeichnung') ^ 4.2,
        NGramField('bezeichnung_ngram') ^ 1.8,
        SimpleField('art') ^ 0.5,
        NGramField('art_ngram') ^ 0.3,
        SimpleField('strasse_name') ^ 1.2,
        ReplaceStrasse(NGramField('strasse_name_ngram') ^ 0.8),
        SimpleField('gemeinde_name') ^ 0.6,
        NGramField('gemeinde_name_ngram') ^ 0.4,
        SimpleField('gemeindeteil_name') ^ 0.8,
        NGramField('gemeindeteil_name_ngram') ^ 0.6,
        # search for housenumbers only in hausnummer
        Only('^\d{1,3}[a-zA-Z]{,2}$', PrefixField('hausnummer', 1)),
        # search for zip codes only in postleitzahl
        Only('^\d{3,5}$', PrefixField('postleitzahl')),
    )
    sort = 'score DESC, gemeinde_name ASC, strasse_name ASC, strasse_schluessel ASC, ' \
        'bezeichnung ASC, hausnummer_int ASC, hausnummer ASC'
    sort_fields = ('gemeinde_name', 'strasse_name')
    collection_rank = 2.5

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        parts.append(prop['bezeichnung'])
        parts.append(prop['art'])
        parts.append(prop['strasse_name'] + ' ' + prop['hausnummer'])
        return ', '.join(parts)


class OrkaApp(Collection):
    class_ = 'orka-app'
    class_title = 'ORKa.MV-App'
    name = 'orka-app'
    title = 'ORKa.MV-App'
    fields = ('name', 'category', 'category_title')
    qfields = (
        SimpleField('name') ^ 4.2,
        NGramField('name_ngram') ^ 1.8,
        SimpleField('category') ^ 0.5,
        NGramField('category_ngram') ^ 0.3,
        SimpleField('category_title') ^ 0.5,
        NGramField('category_title_ngram') ^ 0.3,
    )
    sort = 'score DESC, category ASC, name ASC'
    sort_fields = ('category', 'name')
    collection_rank = 2.5

    def to_title(self, prop):
        if prop['name']:
            parts = []
            parts.append(prop['category_title'])
            parts.append(prop['name'])
            return ', '.join(parts)
        else:
            return prop['category_title']


class Stadtteillotse(Collection):
    class_ = 'stadtteillotse'
    class_title = 'Stadtteillotse Rostock'
    name = 'stadtteillotse'
    title = 'Stadtteillotse Rostock'
    fields = ('name', 'category', 'category_title')
    qfields = (
        SimpleField('name') ^ 4.2,
        NGramField('name_ngram') ^ 1.8,
        SimpleField('category') ^ 0.5,
        NGramField('category_ngram') ^ 0.3,
        SimpleField('category_title') ^ 0.5,
        NGramField('category_title_ngram') ^ 0.3,
    )
    sort = 'score DESC, category ASC, name ASC'
    sort_fields = ('category', 'name')
    collection_rank = 2.5

    def to_title(self, prop):
        if prop['name']:
            parts = []
            parts.append(prop['category_title'])
            parts.append(prop['name'])
            return ', '.join(parts)
        else:
            return prop['category_title']

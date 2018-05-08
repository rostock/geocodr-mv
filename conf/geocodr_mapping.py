# -:- encoding: utf-8 -:-

import re

from geocodr import proj
from geocodr.search import (
    Collection as BaseCollection,
    NGramField,
    SimpleField,
    PrefixField,
    Only,
    PatternReplace,
)

gemarkung_prefix = '13' # Prefix added to 4-digit Gemarkungsnummern (13=Mecklenburg-Vorpommern)

class Collection(BaseCollection):
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
    Wrap field with pattern replace. We replace straße suffix with str (all
    case-insensitive). This is already implemented in the Solr schema, but it
    does not work with our NGramField, as we build the grams on our own.
    A boost must be applied to the field, not this wrapped result.
    """
    return PatternReplace(ur'(?i)stra(ß|ss)e\b', u'str.', field)

class Strassen(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'strassen'
    title = u'Straße'
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
        return u', '.join(parts)


class Adressen(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'adressen'
    title = u'Adresse'
    fields = ('strasse_name', 'gemeindeteil_name', 'gemeinde_name',
              'postleitzahl', 'hausnummer')
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
        # search for hausnumbers only in hausnummer
        Only('^\d{1,3}[a-zA-Z]{,2}$', SimpleField('hausnummer')),
        # search for zip codes only in postleitzahl
        Only('^\d{3,5}$', PrefixField('postleitzahl')),
    )
    sort = 'score DESC, gemeinde_name ASC, strasse_name ASC, ' \
        'hausnummer_int ASC, hausnummer ASC'

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        if prop['gemeindeteil_name']:
            parts.append(prop['gemeindeteil_name'])
        parts.append(prop['strasse_name'] + ' ' + prop['hausnummer'])
        return u', '.join(parts)

    def sort_tiebreaker(self, doc):
        """
        Sort order for docs with same score.
        """
        return (
            doc['gemeindeteil_name'],
            doc['strasse_name'],
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
    title = u'Gemeinde'
    fields = ('gemeinde_name',)
    qfields = (
        NGramField('gemeinde_name_ngram') ^ 2.4,
        # higher then gemeindeteil_name in GemeindeTeile
        SimpleField('gemeinde_name') ^ 4.4,
    )
    sort = 'score DESC, gemeinde_name ASC'
    sort_fields = ('gemeinde_name', )
    collection_rank = 1

    def to_title(self, prop):
        parts = []
        parts.append(prop['gemeinde_name'])
        if prop['gemeinde_name_suchzusatz']:
            parts[-1] += ' ' + prop['gemeinde_name_suchzusatz']
        return u', '.join(parts)


class GemeindeTeile(Collection):
    class_ = 'address'
    class_title = 'Adresse'
    name = 'gemeindeteile'
    title = u'Gemeindeteil'
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
        return u', '.join(parts)


class Gemarkungen(Collection):
    class_ = 'parcel'
    class_title = u'Flurstück'
    name = 'gemarkungen'
    title = u'Gemarkung'
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
        parts.append(prop['gemarkung_name'])
        return u', '.join(parts)

    def query(self, query):
        if re.match(ur'^\d{4,4}$', query):
            query = gemarkung_prefix + query

        return Collection.query(self, query)

class Fluren(Collection):
    class_ = 'parcel'
    class_title = u'Flurstück'
    name = 'fluren'
    title = u'Flur'
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
        parts.append(prop['gemarkung_name'])
        parts.append(u'Flur ' + str(int(prop['flur'], 10)))
        return u', '.join(parts)

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
            qparts.append(u'gemarkung_schluessel:' + flst.gemarkung)

        if flst.flur:
            qparts.append(u'flur:' + flst.flur)

        return u'{}'.format(u' AND '.join(qparts))


class Flurstuecke(Collection):
    class_ = 'parcel'
    class_title = u'Flurstück'
    name = 'flurstuecke'
    title = u'Flurstück'
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
        parts.append(prop['gemarkung_name'])
        parts.append(u'Flur ' + str(int(prop['flur'], 10)))
        parts.append(str(int(prop['zaehler'], 10)))
        if prop['nenner'] != '0000':
            parts[-1] += '/' + str(int(prop['nenner'], 10))
        return u', '.join(parts)

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

        if not flst.gemarkung_name:
            return u'flurstuecksnummer:' + flst.gemarkung + flst.flur \
                + flst.zaehler + flst.nenner + u'*'

        qparts = []
        qparts = [Collection.query(self, flst.gemarkung_name)]

        if flst.flur:
            qparts.append(u'flur:' + flst.flur)
        if flst.nenner:
            qparts.append(u'nenner:' + flst.nenner)
        if flst.zaehler:
            qparts.append(u'zaehler:' + flst.zaehler)

        return u'{}'.format(u' AND '.join(qparts))


class Schulen(Adressen):
    class_ = 'school'
    class_title = 'Schule'
    name = 'schulen'
    title = u'Schule'
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
        # search for hausnumbers only in hausnummer
        Only('^\d{1,3}[a-zA-Z]{,2}$', SimpleField('hausnummer')),
        # search for zip codes only in postleitzahl
        Only('^\d{3,5}$', PrefixField('postleitzahl')),
    )
    sort = 'score DESC, gemeinde_name ASC, strasse_name ASC, bezeichnung ASC, ' \
        'hausnummer_int ASC, hausnummer ASC'
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
        return u', '.join(parts)

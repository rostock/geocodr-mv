#! /usr/bin/env bash

# This script exports various PostgreSQL tables into CSV files for import into
# Solr with geocodr-post.
#
# Usage:
#   The script takes no arguments. Use environment variables to change the
#   output directory and PostgreSQL parameters.
#
# Example:
#   CSV_OUTDIR=/tmp/csv-files PGDATABASE=geocodr PGUSER=geocodr geocodr-pg2csv.sh
#
# Special notes:
#  - Some geometries are simplified
#  - The `json` column in the CSV will contain all columns of the table except
#  the geometry . This allows us to access all columns in the geocoder
#  results without manually adding each column to the Solr index/storage.


CSV_OUTDIR="${CSV_OUTDIR:-/tmp/geocodr-csv}"
export PGDATABASE="${PGDATABASE:-geocodr}"
DBSCHEMA="${DBSCHEMA:-public}"

mkdir -p $CSV_OUTDIR

function pg2csv {
  fname=$1
  q="$2"
  echo writing $fname
  psql --no-psqlrc -c "$q" > $fname
}

pg2csv $CSV_OUTDIR/gemeinden.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemeinde_name,
  ST_Area(geometrie) as gemeinde_flaeche,
  gemeinde_name ilike '%stadt' as gemeinde_ist_stadt,
  to_jsonb(gemeinden_geocodr) - 'geometrie' AS json
FROM basisdaten.gemeinden_geocodr
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/gemeindeteile.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  ST_Area(geometrie) as gemeindeteil_flaeche,
  to_jsonb(gemeindeteile_geocodr) - 'geometrie' AS json
FROM basisdaten.gemeindeteile_geocodr
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/strassen.csv "$(cat << END
COPY (SELECT
  row_number() OVER () AS id,
  ST_AsText(ST_Simplify(s.geometrie, 1)) AS geometrie,
  s.gemeinde_name,
  gemeindeteil_name,
  strasse_name,
  ST_Length(s.geometrie) as strasse_laenge,
  ST_Area(g.geometrie) as gemeinde_flaeche,
  s.gemeinde_name ilike '%stadt' as gemeinde_ist_stadt,
  to_jsonb(s) - 'geometrie' AS json
FROM ${DBSCHEMA}.strassen_alle_mit_gemeindeteil s
LEFT JOIN ${DBSCHEMA}.gemeinden g ON g.gemeinde_schluessel = s.gemeinde_schluessel
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/adressen.csv "$(cat << END
COPY (SELECT
  a.uuid AS id,
  ST_AsText(a.geometrie) AS geometrie,
  strasse_name,
  strasse_schluessel,
  postleitzahl,
  gemeindeteil_name,
  a.gemeinde_name,
  hausnummer AS hausnummer_int,
  hausnummer || coalesce(hausnummer_zusatz, '') AS hausnummer,
  ST_Area(g.geometrie) as gemeinde_flaeche,
  a.gemeinde_name ilike '%stadt' as gemeinde_ist_stadt,
  to_jsonb(a) - 'geometrie' AS json
FROM ${DBSCHEMA}.adressen_alle a
LEFT JOIN ${DBSCHEMA}.gemeinden g ON g.gemeinde_schluessel = a.gemeinde_schluessel
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/gemarkungen.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemarkung_name,
  gemarkung_schluessel,
  gemeinde_name,
  to_jsonb(gemarkungen_geocodr) - 'geometrie' AS json
FROM basisdaten.gemarkungen_geocodr
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/fluren.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 1), 0)) AS geometrie,
  gemarkung_name,
  gemarkung_schluessel,
  gemeinde_name,
  flur,
  to_jsonb(fluren_geocodr) - 'geometrie' AS json
FROM basisdaten.fluren_geocodr
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/flurstuecke.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  CASE
   WHEN ST_IsEmpty(ST_Buffer(ST_Simplify(geometrie, 0.5), 0)) THEN ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.008), 0))
   ELSE ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0))
  END AS geometrie,
  gemarkung_name,
  gemeinde_name,
  flur,
  zaehler,
  nenner,
  flurstuecksnummer,
  flurstueckskennzeichen,
  to_jsonb(flurstuecke_geocodr) - 'geometrie' AS json
FROM basisdaten.flurstuecke_geocodr
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/gemeindeteile_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  ST_Area(geometrie) as gemeindeteil_flaeche,
  to_jsonb(gemeindeteile_geocodr) - 'geometrie' AS json
FROM basisdaten.gemeindeteile_geocodr WHERE kreis_schluessel = '13003'
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/strassen_hro.csv "$(cat << END
COPY (SELECT
  row_number() OVER () AS id,
  ST_AsText(ST_Simplify(geometrie, 1)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  strasse_name,
  ST_Length(geometrie) as strasse_laenge,
  to_jsonb(strassen_alle_mit_gemeindeteil) - 'geometrie' AS json
FROM ${DBSCHEMA}.strassen_alle_mit_gemeindeteil WHERE kreis_schluessel = '13003'
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/adressen_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(geometrie) AS geometrie,
  strasse_name,
  strasse_schluessel,
  postleitzahl,
  gemeindeteil_name,
  gemeinde_name,
  hausnummer AS hausnummer_int,
  hausnummer || coalesce(hausnummer_zusatz, '') AS hausnummer,
  to_jsonb(adressen_hro_geocodr) - 'geometrie' AS json
FROM ${DBSCHEMA}.adressen_hro_geocodr
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/gemarkungen_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemarkung_name,
  gemarkung_schluessel,
  gemeinde_name,
  to_jsonb(gemarkungen_geocodr) - 'geometrie' AS json
FROM basisdaten.gemarkungen_geocodr WHERE kreis_schluessel = '13003'
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/fluren_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 1), 0)) AS geometrie,
  gemarkung_name,
  gemarkung_schluessel,
  gemeinde_name,
  flur,
  to_jsonb(fluren_geocodr) - 'geometrie' AS json
FROM basisdaten.fluren_geocodr WHERE kreis_schluessel = '13003'
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/flurstuecke_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  CASE
   WHEN ST_IsEmpty(ST_Buffer(ST_Simplify(geometrie, 0.5), 0)) THEN ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.01), 0))
   ELSE ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0))
  END AS geometrie,
  gemarkung_name,
  gemeinde_name,
  flur,
  zaehler,
  nenner,
  flurstuecksnummer,
  flurstueckskennzeichen,
  to_jsonb(flurstuecke_geocodr_hro) - 'geometrie' AS json
FROM basisdaten.flurstuecke_geocodr_hro
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/schulen.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(geometrie) AS geometrie,
  bezeichnung,
  art,
  strasse_name,
  strasse_schluessel,
  postleitzahl,
  gemeindeteil_name,
  gemeinde_name,
  hausnummer AS hausnummer_int,
  hausnummer || coalesce(hausnummer_zusatz, '') AS hausnummer,
  to_jsonb(schulen) - 'geometrie' AS json
FROM ${DBSCHEMA}.schulen
) TO STDOUT WITH CSV HEADER;
END
)"

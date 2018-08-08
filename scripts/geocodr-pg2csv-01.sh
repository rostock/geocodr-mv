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
  to_jsonb(gemeinden) - 'geometrie' AS json
FROM ${DBSCHEMA}.gemeinden
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/gemeindeteile.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  to_jsonb(gemeindeteile) - 'geometrie' AS json
FROM ${DBSCHEMA}.gemeindeteile
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/strassen.csv "$(cat << END
COPY (SELECT
  row_number() OVER () AS id,
  ST_AsText(ST_Simplify(geometrie, 1)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  strasse_name,
  to_jsonb(strassen_alle_mit_gemeindeteil) - 'geometrie' AS json
FROM ${DBSCHEMA}.strassen_alle_mit_gemeindeteil
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/adressen.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(geometrie) AS geometrie,
  strasse_name,
  postleitzahl,
  gemeindeteil_name,
  gemeinde_name,
  hausnummer AS hausnummer_int,
  hausnummer || coalesce(hausnummer_zusatz, '') AS hausnummer,
  to_jsonb(adressen_alle) - 'geometrie' AS json
FROM ${DBSCHEMA}.adressen_alle
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
  to_jsonb(gemarkungen_alle) - 'geometrie' AS json
FROM ${DBSCHEMA}.gemarkungen_alle
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
  to_jsonb(fluren_alle) - 'geometrie' AS json
FROM ${DBSCHEMA}.fluren_alle
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/flurstuecke.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  CASE
   WHEN ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0)) ~ 'EMPTY' THEN ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.008), 0))
   ELSE ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0))
  END AS geometrie,
  gemarkung_name,
  gemeinde_name,
  flur,
  zaehler,
  nenner,
  flurstuecksnummer,
  flurstueckskennzeichen,
  to_jsonb(flurstuecke_alle) - 'geometrie' AS json
FROM ${DBSCHEMA}.flurstuecke_alle
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/gemeindeteile_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 5), 0)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  to_jsonb(gemeindeteile) - 'geometrie' AS json
FROM ${DBSCHEMA}.gemeindeteile WHERE kreis_schluessel = '13003'
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
  to_jsonb(gemarkungen_alle) - 'geometrie' AS json
FROM ${DBSCHEMA}.gemarkungen_alle WHERE kreis_schluessel = '13003'
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
  to_jsonb(fluren_alle) - 'geometrie' AS json
FROM ${DBSCHEMA}.fluren_alle WHERE kreis_schluessel = '13003'
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/flurstuecke_hro.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  CASE
   WHEN ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0)) ~ 'EMPTY' THEN ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.01), 0))
   ELSE ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0))
  END AS geometrie,
  gemarkung_name,
  gemeinde_name,
  flur,
  zaehler,
  nenner,
  flurstuecksnummer,
  flurstueckskennzeichen,
  to_jsonb(flurstuecke_hro_geocodr) - 'geometrie' AS json
FROM ${DBSCHEMA}.flurstuecke_hro_geocodr
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

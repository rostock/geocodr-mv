#! /usr/bin/bash

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
FROM gemeinden
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
FROM gemeindeteile
) TO STDOUT WITH CSV HEADER;
END
)"


pg2csv $CSV_OUTDIR/strassen.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Simplify(geometrie, 1)) AS geometrie,
  gemeinde_name,
  gemeindeteil_name,
  strasse_name,
  to_jsonb(strassen_mit_gemeindeteil) - 'geometrie' AS json
FROM strassen_mit_gemeindeteil
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
  to_jsonb(adressen) - 'geometrie' AS json
FROM adressen
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
  to_jsonb(gemarkungen) - 'geometrie' AS json
FROM gemarkungen
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
  to_jsonb(fluren) - 'geometrie' AS json
FROM fluren
) TO STDOUT WITH CSV HEADER;
END
)"

pg2csv $CSV_OUTDIR/flurstuecke.csv "$(cat << END
COPY (SELECT
  uuid AS id,
  ST_AsText(ST_Buffer(ST_Simplify(geometrie, 0.5), 0)) AS geometrie,
  gemarkung_name,
  gemeinde_name,
  flur,
  zaehler,
  nenner,
  flurstuecksnummer,
  flurstueckskennzeichen,
  to_jsonb(flurstuecke) - 'geometrie' AS json
FROM flurstuecke
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
FROM schulen
) TO STDOUT WITH CSV HEADER;
END
)"


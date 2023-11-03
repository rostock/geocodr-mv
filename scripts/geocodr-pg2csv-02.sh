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

pg2csv $CSV_OUTDIR/orka-app.csv "$(cat << END
COPY (SELECT
  id,
  ST_AsText(geometrie) AS geometrie,
  name,
  category,
  category_title,
  to_jsonb(geocodr) - 'geometrie' AS json
FROM ${DBSCHEMA}.geocodr WHERE orka_app IS TRUE AND category IS NOT NULL
) TO STDOUT WITH CSV HEADER;
END
)"

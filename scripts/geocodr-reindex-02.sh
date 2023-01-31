#! /usr/bin/env bash

set -e # exit on error
set -u # strict mode

# Export data from PostgreSQL as CSV and post data into SolrCloud.
# Set environment variables to configure DB parameters:
#
# % CSV_OUTDIR=/tmp/geocodr-csv PGHOST=server PGDATABASE=data PGUSER=dbuser PGPASSWORD=pw DBSCHEMA=public geocodr-reindex.sh

/usr/local/geocodr-mv/geocodr-mv/scripts/geocodr-pg2csv-02.sh

cat <<EOF | xargs -I % /usr/local/geocodr-mv/virtualenv/bin/geocodr-post --url http://localhost:8983/solr --csv $CSV_OUTDIR/%.csv --collection %
orka-app
stadtteillotse
EOF


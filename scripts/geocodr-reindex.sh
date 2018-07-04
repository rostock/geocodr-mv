#! /usr/bin/env bash

set -e # exit on error
set -u # strict mode

# Export data from PostgreSQL as CSV and post data into SolrCloud.
# Set environment variables to configure DB parameters:
#
# % CSV_OUTDIR=/tmp/geocodr-csv PGHOST=server PGDATABASE=data PGUSER=dbuser PGPASSWORD=pw DBSCHEMA=public geocodr-reindex.sh

/usr/local/geocodr-mv/scripts/geocodr-pg2csv.sh

cat <<EOF | xargs -I % /usr/local/geocodr/bin/geocodr-post --url http://localhost:8983/solr --csv $CSV_OUTDIR/%.csv --collection %
schulen
adressen
fluren
gemarkungen
gemeinden
gemeindeteile
strassen
flurstuecke
adressen_hro
fluren_hro
gemarkungen_hro
gemeindeteile_hro
strassen_hro
flurstuecke_hro
EOF


#! /usr/bin/env bash

set -e # exit on error
set -u # strict mode

# Export data from PostgreSQL as CSV and post data into SolrCloud.
# Set environment variables to configure DB parameters:
#
# % CSV_OUTDIR=/tmp/geocodr-csv $CSV_INDIR=/tmp/geocodr-csv PGHOST=server PGDATABASE=data PGUSER=dbuser PGPASSWORD=pw DBSCHEMA=public geocodr-reindex.sh

/usr/local/geocodr-mv/geocodr-mv/scripts/geocodr-pg2csv-01.sh

cat <<EOF | xargs -I % /usr/local/geocodr-mv/virtualenv/bin/geocodr-post --url http://localhost:8983/solr --csv $CSV_INDIR/%.csv --collection %
flurstueckseigentuemer
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
postleitzahlengebiete
EOF


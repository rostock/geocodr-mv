# *geocodr-mv*

A [*geocodr*](https://github.com/rostock/geocodr) configuration for Mecklenburg-Vorpommern

## Directories and files

- `scripts/geocodr-pg2csv.sh`: script to dump *PostgreSQL* tables as CSV for import with `geocodr-post`
- `scripts/geocodr-reindex.sh`: script to call `geocodr-pg2csv.sh` and to import the data with `geocodr-post`
- `conf/geocodr_mapping.py`: *geocodr* mapping with multiple customized classes and collections
- `server/INSTALL.rst`: installation documentation for a two server setup based on SLES 15
- `server/`: configuration and installation files
- `solr/`: *Apache Solr* configuration and schemas for all collections for `geocodr-zk`
- `tests/`: acceptance tests for this *geocodr* configuration

## Add new collections

The following steps are required to add a new collection. We use the collection `sport` for gyms, swimming pools, pitches etc. as an example:

- Edit `geocodr-pg2csv.sh` to create a new `sport.csv`. Create a `SELECT` that queries all data you want to import into that collection. You can use `UNION` to query from multiple tables. Complex joins are also possible. Make sure the selected columns have the same name as the `field` in your *Apache Solr* schema (use `AS` if that is not the case).
- Create a `sport-schema.xml` file. Add a field for each property that should be indexed. Create an additional `_ngram` field for fuzzy search and make sure this field is filled as well (`copyField`). See `address-schema.xml` for a documented *Apache Solr* schema with special field types for street names, etc.
- Upload schema: `geocodr-zk --zk-hosts localhost:9983 --config-dir solr/ --push sport`
- Create CSV dump: `CSV_OUTDIR=/tmp/csv-files CSV_INDIR=/tmp/csv-files PGDATABASE=geocodr PGUSER=geocodr scripts/geocodr-pg2csv.sh`
- Index data: `geocodr-post --url http://localhost:8983/solr --csv /tmp/csv-files/sport.csv --collection sport`
- Add `sport` to `geocodr-reindex.sh` for automatic updates.
- Create a `Sport` class for your collection in `conf/geocodr-mapping.py`.
- Reload Geocodr
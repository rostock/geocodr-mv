Installation of *geocodr* with *SolrCloud*
==========================================

This documentation describes the installation of *geocodr* with *SolrCloud* on two SLES 15 servers.
The server names are ``svc15`` and ``svc16``.


Configuration
-------------

You need to update ``conf/zoo.cfg`` and ``conf/solr-defaults`` with the hostnames of your servers.
Also check the other configurations if there are any changes necessary.

Preparation
-----------

Prepare each server by creating a (temporary) directory for installation packages and configurations.
Then copy all files::


    seq 10 12 | xargs -I % ssh svc% mkdir -p geocodr
    seq 10 12 | xargs -I % scp -r install* conf pkgs svc%:geocodr/

Installation and setup of *SolrCloud* and *ZooKeeper*
-----------------------------------------------------

Login to each server and repeat the following steps.

Install packages::

    sudo zypper install python3-devel postgresql java-11-openjdk-headless
    PREFIX=/usr/local PKGS=/home/username/geocodr/pkgs sudo -E bash solr/install_zookeeper.sh
    PREFIX=/usr/local PKGS=/home/username/geocodr/pkgs sudo -E bash solr/install_solr.sh

Create users::

    sudo useradd -g daemon --system -d /var/lib/solr solr
    sudo useradd -g daemon --system -d /usr/local/geocodr-mv geocodr

Create directories and base config for both *Solr* and *ZooKeeper*::

    sudo mkdir -p /data/solr
    sudo cp /usr/local/solr/server/solr/solr.xml /data/solr/

    sudo mkdir -p /var/log/{solr,zookeeper}
    sudo mkdir -p /var/run/solr
    sudo mkdir -p /var/lib/zookeeper

    # replace 1 with server number from zoo.cfg
    echo '1' | sudo tee /var/lib/zookeeper/myid

    sudo cp geocodr/conf/zoo.cfg /usr/local/zookeeper/conf
    sudo chown -R solr:daemon /data/solr /usr/local/solr* /usr/local/zookeeper* /var/log/solr /var/run/solr /var/log/zookeeper /var/lib/zookeeper

    sudo cp geocodr/conf/solr-defaults /etc/default/solr
    sudo cp geocodr/conf/zookeeper-defaults /etc/default/zookeeper
    sudo chown 0755 /etc/default/{solr,zookeeper}

Configure *systemd* and start both *Solr* and *ZooKeeper*::

    sudo cp geocodr/conf/{solr,zookeeper}.service /etc/systemd/system/
    sudo chmod 644 /etc/systemd/system/{solr,zookeeper}.service
    sudo chown root:root /etc/systemd/system/{solr,zookeeper}.service
    sudo systemctl daemon-reload
    sudo systemctl enable zookeeper
    sudo systemctl start zookeeper
    sudo systemctl enable solr
    sudo systemctl start solr

Installation and setup of *geocodr*
-----------------------------------

Install *geocodr* (on one or more servers)::

    sudo pyvenv /usr/local/geocodr
    sudo -E /usr/local/geocodr/bin/pip install -r geocodr/conf/requirements-api.txt
    sudo -E /usr/local/geocodr/bin/pip install -r geocodr/conf/requirements-import.txt
    sudo -E /usr/local/geocodr/bin/pip install geocodr/pkgs/geocodr-1.0.0-py2.py3-none-any.whl
    sudo -E /usr/local/geocodr/bin/pip install geocodr/pkgs/geocodr_import-1.0.0-py2.py3-none-any.whl

Install *geocodr* configuration::

    sudo -E git clone https://github.com/rostock/geocodr-mv.git /usr/local/geocodr-mv

Setup *SolrCloud* and *ZooKeeper* (only required on one server)::

    /usr/local/geocodr/bin/geocodr-zk --zk-hosts localhost:2181 --config-dir /usr/local/geocodr-mv/solr --push ALL

Configure *systemd* and start *geocodr* API::

    sudo cp geocodr/conf/geocodr-api.service /etc/systemd/system/
    sudo chmod 644 /etc/systemd/system/geocodr-api.service
    sudo chown root:root /etc/systemd/system/geocodr-api.service
    sudo systemctl daemon-reload
    sudo systemctl enable geocodr-api
    sudo systemctl start geocodr-api

Automatic reindex
-----------------

Create ``/etc/cron.d/geocodr-reindex`` to automatically reindex data every night::


    32 3 * * * geocodr export CSV_OUTDIR=/tmp/geocodr-csv PGHOST=localhost PGDATABASE=data PGUSER=user PGPASSWORD=password DBSCHEMA=public; /usr/local/geocodr-mv/scripts/geocodr-reindex.sh >> /var/log/geocodr/reindex.log 2>&1


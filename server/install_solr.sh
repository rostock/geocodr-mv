#! /usr/bin/env bash

# This script downloads and installs Solr including JTS.
# Set PREFIX to change install location, set PKGS to change pkg download directory:
#
# % PREFIX=/usr/local PKGS=~/pkgs ./install_solr.sh

set -e # exit on error
set -u # strict mode
set -x

PREFIX=${PREFIX:-/opt}
PKGS=${PKGS:-/opt/pkgs}

SOLR_VERSION=7.3.0
SOLR_PKG=${PKGS}/solr-${SOLR_VERSION}.tgz
SOLR_URL=http://archive.apache.org/dist/lucene/solr/${SOLR_VERSION}/solr-${SOLR_VERSION}.tgz

JTS_CORE_VERSION=1.15.0
JTS_CORE_PKG=${PKGS}/jts-core-${JTS_CORE_VERSION}.jar
JTS_CORE_URL=https://repo.maven.apache.org/maven2/org/locationtech/jts/jts-core/${JTS_CORE_VERSION}/jts-core-${JTS_CORE_VERSION}.jar

SOLR_INSTALL_BASE=${PREFIX}/solr-${SOLR_VERSION}
SOLR_BASE=${PREFIX}/solr

# install location for JTS-core
SOLR_WEBINF_LIB=${SOLR_INSTALL_BASE}/server/solr-webapp/webapp/WEB-INF/lib/

if [[ ! -d ${SOLR_INSTALL_BASE} ]]; then
  if [[ ! -e ${SOLR_PKG} ]]; then
    curl -fsSL ${SOLR_URL} -o ${SOLR_PKG}
  fi

  tar -xzf ${SOLR_PKG} -C ${PREFIX}
  ln -sf ${SOLR_INSTALL_BASE} ${SOLR_BASE}



fi
if [[ ! -e ${JTS_CORE_PKG} ]]; then
  curl -fsSL ${JTS_CORE_URL} -o ${JTS_CORE_PKG}
fi
cp ${JTS_CORE_PKG} ${SOLR_WEBINF_LIB}


#! /usr/bin/env bash

# This script downloads and installs Zookeeper.
# Set PREFIX to change install location, set PKGS to change pkg download directory:
#
# % PREFIX=/usr/local PKGS=~/pkgs ./install_zookeeper.sh

set -e # exit on error
set -u # strict mode
set -x

PREFIX=${PREFIX:-/opt}
PKGS=${PKGS:-/opt/pkgs}

ZK_VERSION=3.4.11
ZK_PKG=${PKGS}/zookeeper-${ZK_VERSION}.tar.gz
ZK_URL=https://archive.apache.org/dist/zookeeper/zookeeper-${ZK_VERSION}/zookeeper-${ZK_VERSION}.tar.gz

ZK_INSTALL_BASE=${PREFIX}/zookeeper-${ZK_VERSION}
ZK_BASE=${PREFIX}/zookeeper

if [[ ! -d ${ZK_INSTALL_BASE} ]]; then
  if [[ ! -e ${ZK_PKG} ]]; then
    curl -fsSL ${ZK_URL} -o ${ZK_PKG}
  fi
  tar -zxf ${ZK_PKG} -C ${PREFIX}
  ln -sf ${ZK_INSTALL_BASE} ${ZK_BASE}
fi


#!/usr/bin/env bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  docker.io \
  git \
  jq

if ! apt-get install -y --no-install-recommends docker-compose-plugin; then
  apt-get install -y --no-install-recommends docker-compose
fi

systemctl enable docker
systemctl start docker

mkdir -p /srv/clipsbot

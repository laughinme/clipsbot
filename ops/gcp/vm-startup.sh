#!/usr/bin/env bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

install_docker_compose_plugin() {
  if docker compose version >/dev/null 2>&1; then
    return 0
  fi

  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64|amd64)
      arch="x86_64"
      ;;
    aarch64|arm64)
      arch="aarch64"
      ;;
    *)
      echo "Unsupported architecture for docker compose plugin: ${arch}"
      return 1
      ;;
  esac

  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL \
    "https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-${arch}" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  docker compose version >/dev/null
}

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

install_docker_compose_plugin

systemctl enable docker
systemctl start docker

mkdir -p /srv/clipsbot

#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${1:-archive-state}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-clipsbot-local}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-knowledge_corpus_restored_http}"

PG_DUMP="${STATE_DIR}/templatepg_test.dump"
QDRANT_SNAPSHOT="${STATE_DIR}/knowledge_corpus_restored_http.snapshot"
MEDIA_TARBALL="${STATE_DIR}/clipsbot-media-private.tar"

if [[ ! -f "${PG_DUMP}" ]]; then
  echo "Missing Postgres dump: ${PG_DUMP}" >&2
  exit 1
fi

if [[ ! -f "${QDRANT_SNAPSHOT}" ]]; then
  echo "Missing Qdrant snapshot: ${QDRANT_SNAPSHOT}" >&2
  exit 1
fi

if [[ ! -f "${MEDIA_TARBALL}" ]]; then
  echo "Missing MinIO media tarball: ${MEDIA_TARBALL}" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi
touch frontend/.env bot/.env
if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
fi

if ! grep -q '^QDRANT_COLLECTION=' .env; then
  printf '\nQDRANT_COLLECTION=%s\n' "${QDRANT_COLLECTION}" >> .env
fi
if ! grep -q '^QDRANT_COLLECTION=' backend/.env; then
  printf '\nQDRANT_COLLECTION=%s\n' "${QDRANT_COLLECTION}" >> backend/.env
fi

echo "Starting stateful services..."
docker compose -p "${PROJECT_NAME}" up -d db redis rabbitmq minio minio-init qdrant

DB_CID=""
until [[ -n "${DB_CID}" ]] && docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "${DB_CID}" 2>/dev/null | grep -q healthy; do
  DB_CID="$(docker compose -p "${PROJECT_NAME}" ps -q db || true)"
  sleep 2
done

until curl -fsS http://127.0.0.1:6333/collections >/dev/null 2>&1; do
  sleep 2
done

until curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; do
  sleep 2
done

echo "Restoring Postgres..."
docker cp "${PG_DUMP}" "${DB_CID}:/tmp/templatepg.dump"
docker exec "${DB_CID}" sh -lc 'pg_restore --clean --if-exists --no-owner -U postgres -d templatepg /tmp/templatepg.dump'

echo "Restoring Qdrant collection ${QDRANT_COLLECTION}..."
curl -fsS -X POST \
  "http://127.0.0.1:6333/collections/${QDRANT_COLLECTION}/snapshots/upload?priority=snapshot" \
  -F "snapshot=@${QDRANT_SNAPSHOT}" >/dev/null

until curl -fsS "http://127.0.0.1:6333/collections/${QDRANT_COLLECTION}" >/dev/null 2>&1; do
  sleep 2
done

echo "Restoring MinIO media..."
RESTORE_TMP="$(mktemp -d)"
trap 'rm -rf "${RESTORE_TMP}"' EXIT
tar -xf "${MEDIA_TARBALL}" -C "${RESTORE_TMP}"

docker run --rm --network "${PROJECT_NAME}_default" \
  -v "${RESTORE_TMP}:/restore:ro" \
  --entrypoint /bin/sh \
  minio/mc -lc '
    mc alias set local http://minio:9000 minioadmin minioadmin >/dev/null &&
    mc mb --ignore-existing local/media-private >/dev/null &&
    mc mirror --overwrite /restore/media-private local/media-private
  '

echo "Starting application services..."
docker compose -p "${PROJECT_NAME}" up -d --build \
  backend scheduler worker-sync worker-index worker-enrich worker-clips bot frontend nginx

echo "Restore complete."
echo "UI: http://localhost/archive"
echo "Smoke test:"
echo "curl -s http://localhost/api/v1/archive/sources"

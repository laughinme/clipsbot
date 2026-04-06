#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export COPYFILE_DISABLE=1

load_env_file() {
  local env_path="$1"
  python3 - "${env_path}" <<'PY'
import pathlib
import shlex
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    print(f"export {key}={shlex.quote(value)}")
PY
}

eval "$(load_env_file "${ROOT_DIR}/.env")"
eval "$(load_env_file "${ROOT_DIR}/backend/.env")"

INSTANCE_NAME="${INSTANCE_NAME:-clipsbot-archive}"
ZONE="${ZONE:-us-central1-a}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-4}"
BOOT_DISK_SIZE_GB="${BOOT_DISK_SIZE_GB:-100}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value core/project 2>/dev/null)}"
EXPORT_DIR="${EXPORT_DIR:-/Users/laughinme/Downloads/AyuGram Desktop/ChatExport_2026-03-23}"
SKIP_EXPORT_SYNC="${SKIP_EXPORT_SYNC:-false}"
SKIP_STATE_SYNC="${SKIP_STATE_SYNC:-false}"
STATE_DIR="${STATE_DIR:-/tmp/clipsbot-gcp-state}"
PG_DUMP_PATH="${PG_DUMP_PATH:-${STATE_DIR}/templatepg_test.dump}"
QDRANT_SNAPSHOT_PATH="${QDRANT_SNAPSHOT_PATH:-${STATE_DIR}/knowledge_corpus_restored_http.snapshot}"
MINIO_MEDIA_DIR="${MINIO_MEDIA_DIR:-${STATE_DIR}/media-private}"
MINIO_MEDIA_TARBALL="${MINIO_MEDIA_TARBALL:-/tmp/clipsbot-media-private.tar}"
RESTORE_QDRANT_COLLECTION="${RESTORE_QDRANT_COLLECTION:-knowledge_corpus_restored_http}"
REMOTE_ROOT="/srv/clipsbot"
REMOTE_IMPORT_ROOT="${REMOTE_ROOT}/imports"
REMOTE_STAGING="~/clipsbot-stage"
REPO_TARBALL="/tmp/clipsbot-cloud-repo.tar.gz"
EXPORT_TARBALL="/tmp/clipsbot-telegram-export.tar"
ADC_JSON_SOURCE="${ADC_JSON_SOURCE:-${HOME}/.config/gcloud/application_default_credentials.json}"
ADC_JSON_TMP="/tmp/clipsbot-cloud-adc.json"
SKIP_ADC_SYNC="${SKIP_ADC_SYNC:-false}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-}"
GCLOUD_SSH_FLAGS=(--project "${PROJECT_ID}" --zone "${ZONE}" --quiet --force-key-file-overwrite)

if [[ -z "${PROJECT_ID}" ]]; then
  echo "PROJECT_ID is required."
  exit 1
fi

if [[ "${SKIP_EXPORT_SYNC}" != "true" && ! -d "${EXPORT_DIR}" ]]; then
  echo "EXPORT_DIR does not exist: ${EXPORT_DIR}"
  exit 1
fi

if [[ "${SKIP_STATE_SYNC}" != "true" ]]; then
  if [[ ! -f "${PG_DUMP_PATH}" ]]; then
    echo "PG_DUMP_PATH does not exist: ${PG_DUMP_PATH}"
    exit 1
  fi
  if [[ ! -f "${QDRANT_SNAPSHOT_PATH}" ]]; then
    echo "QDRANT_SNAPSHOT_PATH does not exist: ${QDRANT_SNAPSHOT_PATH}"
    exit 1
  fi
  if [[ ! -d "${MINIO_MEDIA_DIR}" ]]; then
    echo "MINIO_MEDIA_DIR does not exist: ${MINIO_MEDIA_DIR}"
    exit 1
  fi
fi

required_tools=(gcloud tar)
for tool in "${required_tools[@]}"; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "Missing required tool: ${tool}"
    exit 1
  fi
done

gcloud services enable \
  compute.googleapis.com \
  aiplatform.googleapis.com \
  vision.googleapis.com \
  speech.googleapis.com \
  storage.googleapis.com \
  --project "${PROJECT_ID}"

if ! gcloud compute firewall-rules describe clipsbot-allow-http --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute firewall-rules create clipsbot-allow-http \
    --project "${PROJECT_ID}" \
    --allow tcp:80 \
    --target-tags http-server \
    --direction INGRESS \
    --source-ranges 0.0.0.0/0
fi

if ! gcloud compute firewall-rules describe clipsbot-allow-https --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute firewall-rules create clipsbot-allow-https \
    --project "${PROJECT_ID}" \
    --allow tcp:443 \
    --target-tags http-server \
    --direction INGRESS \
    --source-ranges 0.0.0.0/0
fi

INSTANCE_EXISTS="$(
  gcloud compute instances list \
    --project "${PROJECT_ID}" \
    --filter="name=${INSTANCE_NAME} AND zone:(${ZONE})" \
    --format="value(name)"
)"

if [[ -z "${INSTANCE_EXISTS}" ]]; then
  create_args=(
    compute instances create "${INSTANCE_NAME}"
    --project "${PROJECT_ID}"
    --zone "${ZONE}"
    --machine-type "${MACHINE_TYPE}"
    --boot-disk-size "${BOOT_DISK_SIZE_GB}GB"
    --boot-disk-type "pd-balanced"
    --image-family "ubuntu-2204-lts"
    --image-project "ubuntu-os-cloud"
    --tags "http-server"
    --scopes "https://www.googleapis.com/auth/cloud-platform"
    --metadata-from-file "startup-script=${ROOT_DIR}/ops/gcp/vm-startup.sh"
  )
  if [[ -n "${SERVICE_ACCOUNT}" ]]; then
    create_args+=(--service-account "${SERVICE_ACCOUNT}")
  fi
  gcloud --quiet "${create_args[@]}"
fi

echo "Waiting for SSH availability..."
until gcloud compute ssh "${INSTANCE_NAME}" "${GCLOUD_SSH_FLAGS[@]}" --command "echo ok" >/dev/null 2>&1; do
  sleep 5
done

EXTERNAL_IP="$(
  gcloud compute instances describe "${INSTANCE_NAME}" \
    --project "${PROJECT_ID}" \
    --zone "${ZONE}" \
    --format="value(networkInterfaces[0].accessConfigs[0].natIP)"
)"
PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-${EXTERNAL_IP}.sslip.io}"

mkdir -p /tmp/clipsbot-cloud
cat > /tmp/clipsbot-cloud/.env <<EOF
COMPOSE_PROJECT_NAME=clipsbot
COMPOSE_PROFILES=edge
PUBLIC_HOSTNAME=${PUBLIC_HOSTNAME}
NGINX_HTTP_PORT=8081
SITE_URL=https://${PUBLIC_HOSTNAME}
WEBAPP_URL=https://${PUBLIC_HOSTNAME}/admin
STORAGE_ENDPOINT_PUBLIC=https://${PUBLIC_HOSTNAME}
CADDY_EMAIL=${CADDY_EMAIL:-}
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME:-clips}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID:-}
INTERNAL_BOT_TOKEN=${INTERNAL_BOT_TOKEN:-change-me-internal-bot-token}
AUTH_DEFAULT_ROLE_SLUG=${AUTH_DEFAULT_ROLE_SLUG:-}
BOOTSTRAP_ADMIN_TELEGRAM_IDS=${BOOTSTRAP_ADMIN_TELEGRAM_IDS:-}
CSRF_HMAC_KEY=${CSRF_HMAC_KEY:-change-me}
JWT_PRIVATE_KEY_PATH=./secrets/jwt_private_key.pem
JWT_PUBLIC_KEY_PATH=./secrets/jwt_public_key.pem
ARCHIVE_IMPORT_HOST_ROOT=${REMOTE_IMPORT_ROOT}
ARCHIVE_IMPORT_CONTAINER_ROOT=/imports
ARCHIVE_IMPORT_ALLOWED_ROOTS=/imports
EMBEDDING_PROVIDER=${EMBEDDING_PROVIDER:-vertex}
GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID}}
GOOGLE_CLOUD_LOCATION=${GOOGLE_CLOUD_LOCATION:-us-central1}
GOOGLE_APPLICATION_CREDENTIALS=
GOOGLE_APPLICATION_CREDENTIALS_HOST=/tmp/adc-missing.json
GEMINI_EMBEDDING_MODEL=${GEMINI_EMBEDDING_MODEL:-gemini-embedding-2-preview}
GEMINI_SUMMARY_MODEL=${GEMINI_SUMMARY_MODEL:-gemini-2.5-flash}
OCR_PROVIDER=${OCR_PROVIDER:-vision}
TRANSCRIPT_PROVIDER=${TRANSCRIPT_PROVIDER:-speech_v2}
SUMMARY_PROVIDER=${SUMMARY_PROVIDER:-vertex}
GCS_STAGING_BUCKET=${GCS_STAGING_BUCKET:-${PROJECT_ID}-clipsbot-archive-staging}
GCS_STAGING_LOCATION=${GCS_STAGING_LOCATION:-us-central1}
GCS_STAGING_AUTO_CREATE_BUCKET=${GCS_STAGING_AUTO_CREATE_BUCKET:-true}
TRANSCRIPT_LANGUAGE_CODES=${TRANSCRIPT_LANGUAGE_CODES:-ru-RU,en-US}
STT_SHORT_MODEL=${STT_SHORT_MODEL:-latest_short}
STT_LONG_MODEL=${STT_LONG_MODEL:-latest_long}
EMBEDDING_VECTOR_SIZE=${EMBEDDING_VECTOR_SIZE:-3072}
QDRANT_ENABLED=true
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=${QDRANT_COLLECTION:-${RESTORE_QDRANT_COLLECTION}}
NEXT_PUBLIC_API_BASE_URL=
EOF

cp /tmp/clipsbot-cloud/.env /tmp/clipsbot-cloud/backend.env

tar_args=()
if tar --help 2>&1 | grep -q -- "--disable-copyfile"; then
  tar_args+=(--disable-copyfile)
fi

if ((${#tar_args[@]})); then
  tar \
    "${tar_args[@]}" \
    --exclude="./.git" \
    --exclude="./._*" \
    --exclude="*/._*" \
    --exclude="./.DS_Store" \
    --exclude="*/.DS_Store" \
    --exclude="./frontend/node_modules" \
    --exclude="./frontend/.next" \
    --exclude="./backend/.venv" \
    --exclude="./backend/.pytest_cache" \
    --exclude="./backend/.qdrant-restored" \
    --exclude="*/__pycache__" \
    --exclude="*.pyc" \
    --exclude="./frontend/.turbo" \
    -czf "${REPO_TARBALL}" \
    -C "${ROOT_DIR}" .
else
  tar \
    --exclude="./.git" \
    --exclude="./._*" \
    --exclude="*/._*" \
    --exclude="./.DS_Store" \
    --exclude="*/.DS_Store" \
    --exclude="./frontend/node_modules" \
    --exclude="./frontend/.next" \
    --exclude="./backend/.venv" \
    --exclude="./backend/.pytest_cache" \
    --exclude="./backend/.qdrant-restored" \
    --exclude="*/__pycache__" \
    --exclude="*.pyc" \
    --exclude="./frontend/.turbo" \
    -czf "${REPO_TARBALL}" \
    -C "${ROOT_DIR}" .
fi

if [[ "${SKIP_EXPORT_SYNC}" != "true" ]]; then
  tar -cf "${EXPORT_TARBALL}" -C "$(dirname "${EXPORT_DIR}")" "$(basename "${EXPORT_DIR}")"
fi

if [[ "${SKIP_STATE_SYNC}" != "true" ]]; then
  rm -f "${MINIO_MEDIA_TARBALL}"
  tar -cf "${MINIO_MEDIA_TARBALL}" -C "${STATE_DIR}" "$(basename "${MINIO_MEDIA_DIR}")"
fi

gcloud compute ssh "${INSTANCE_NAME}" \
  "${GCLOUD_SSH_FLAGS[@]}" \
  --command "mkdir -p ${REMOTE_STAGING}"

gcloud compute scp --quiet --force-key-file-overwrite "${REPO_TARBALL}" "${INSTANCE_NAME}:${REMOTE_STAGING}/repo.tar.gz" \
  --project "${PROJECT_ID}" \
  --zone "${ZONE}"
if [[ "${SKIP_EXPORT_SYNC}" != "true" ]]; then
  gcloud compute scp --quiet --force-key-file-overwrite "${EXPORT_TARBALL}" "${INSTANCE_NAME}:${REMOTE_STAGING}/telegram-export.tar" \
    --project "${PROJECT_ID}" \
    --zone "${ZONE}"
fi
if [[ "${SKIP_STATE_SYNC}" != "true" ]]; then
  gcloud compute scp --quiet --force-key-file-overwrite "${PG_DUMP_PATH}" "${INSTANCE_NAME}:${REMOTE_STAGING}/templatepg.dump" \
    --project "${PROJECT_ID}" \
    --zone "${ZONE}"
  gcloud compute scp --quiet --force-key-file-overwrite "${QDRANT_SNAPSHOT_PATH}" "${INSTANCE_NAME}:${REMOTE_STAGING}/qdrant.snapshot" \
    --project "${PROJECT_ID}" \
    --zone "${ZONE}"
  gcloud compute scp --quiet --force-key-file-overwrite "${MINIO_MEDIA_TARBALL}" "${INSTANCE_NAME}:${REMOTE_STAGING}/media-private.tar" \
    --project "${PROJECT_ID}" \
    --zone "${ZONE}"
fi
gcloud compute scp --quiet --force-key-file-overwrite /tmp/clipsbot-cloud/.env "${INSTANCE_NAME}:${REMOTE_STAGING}/.env" \
  --project "${PROJECT_ID}" \
  --zone "${ZONE}"
gcloud compute scp --quiet --force-key-file-overwrite /tmp/clipsbot-cloud/backend.env "${INSTANCE_NAME}:${REMOTE_STAGING}/backend.env" \
  --project "${PROJECT_ID}" \
  --zone "${ZONE}"

if [[ "${SKIP_ADC_SYNC}" != "true" && -f "${ADC_JSON_SOURCE}" ]]; then
  cp "${ADC_JSON_SOURCE}" "${ADC_JSON_TMP}"
  gcloud compute scp --quiet --force-key-file-overwrite "${ADC_JSON_TMP}" "${INSTANCE_NAME}:${REMOTE_STAGING}/application_default_credentials.json" \
    --project "${PROJECT_ID}" \
    --zone "${ZONE}"
  rm -f "${ADC_JSON_TMP}"
fi

gcloud compute ssh "${INSTANCE_NAME}" \
  "${GCLOUD_SSH_FLAGS[@]}" \
  --command "
    set -euxo pipefail
    install_docker_compose_plugin() {
      if sudo docker compose version >/dev/null 2>&1; then
        return 0
      fi

      arch=\$(uname -m)
      case \"\${arch}\" in
        x86_64|amd64)
          arch='x86_64'
          ;;
        aarch64|arm64)
          arch='aarch64'
          ;;
        *)
          echo 'Unsupported architecture for docker compose plugin: '\${arch}
          return 1
          ;;
      esac

      sudo mkdir -p /usr/local/lib/docker/cli-plugins
      sudo curl -fsSL \
        \"https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-\${arch}\" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
      sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
      sudo docker compose version >/dev/null
    }

    install_docker_compose_plugin || true

    COMPOSE_CMD='sudo docker compose'
    if ! sudo docker compose version >/dev/null 2>&1; then
      COMPOSE_CMD='sudo docker-compose'
    fi
    sudo mkdir -p ${REMOTE_ROOT} ${REMOTE_IMPORT_ROOT}
    sudo mkdir -p ${REMOTE_ROOT}/adc
    sudo chown -R \$USER:\$USER ${REMOTE_ROOT}
    cd ${REMOTE_ROOT}
    rm -rf app
    mkdir -p app
    cp ${REMOTE_STAGING}/repo.tar.gz ${REMOTE_ROOT}/repo.tar.gz
    if [ -f ${REMOTE_STAGING}/telegram-export.tar ]; then
      cp ${REMOTE_STAGING}/telegram-export.tar ${REMOTE_ROOT}/telegram-export.tar
    fi
    if [ -f ${REMOTE_STAGING}/templatepg.dump ]; then
      cp ${REMOTE_STAGING}/templatepg.dump ${REMOTE_ROOT}/templatepg.dump
    fi
    if [ -f ${REMOTE_STAGING}/qdrant.snapshot ]; then
      cp ${REMOTE_STAGING}/qdrant.snapshot ${REMOTE_ROOT}/qdrant.snapshot
    fi
    if [ -f ${REMOTE_STAGING}/media-private.tar ]; then
      cp ${REMOTE_STAGING}/media-private.tar ${REMOTE_ROOT}/media-private.tar
    fi
    cp ${REMOTE_STAGING}/.env ${REMOTE_ROOT}/.env
    cp ${REMOTE_STAGING}/backend.env ${REMOTE_ROOT}/backend.env
    if [ -f ${REMOTE_STAGING}/application_default_credentials.json ]; then
      cp ${REMOTE_STAGING}/application_default_credentials.json ${REMOTE_ROOT}/adc/application_default_credentials.json
    else
      touch ${REMOTE_ROOT}/adc/application_default_credentials.json
    fi
    tar -xzf ${REMOTE_ROOT}/repo.tar.gz -C app
    if [ -f ${REMOTE_ROOT}/telegram-export.tar ]; then
      tar -xf ${REMOTE_ROOT}/telegram-export.tar -C ${REMOTE_IMPORT_ROOT}
    fi
    if [ -f ${REMOTE_ROOT}/media-private.tar ]; then
      rm -rf ${REMOTE_ROOT}/restore
      mkdir -p ${REMOTE_ROOT}/restore
      tar -xf ${REMOTE_ROOT}/media-private.tar -C ${REMOTE_ROOT}/restore
    fi
    cp ${REMOTE_ROOT}/.env app/.env
    cp ${REMOTE_ROOT}/backend.env app/backend/.env
    cd app
    \$COMPOSE_CMD up -d --build db redis rabbitmq minio minio-init qdrant
    DB_CID=\"\$(\$COMPOSE_CMD ps -q db)\"
    until [ -n \"\${DB_CID}\" ] && sudo docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' \"\${DB_CID}\" 2>/dev/null | grep -q healthy; do
      sleep 2
      DB_CID=\"\$(\$COMPOSE_CMD ps -q db)\"
    done
    until curl -fsS http://127.0.0.1:6333/collections >/dev/null 2>&1; do sleep 2; done
    until curl -fsS http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; do sleep 2; done
    if [ -f ${REMOTE_ROOT}/templatepg.dump ]; then
      sudo docker cp ${REMOTE_ROOT}/templatepg.dump \"\${DB_CID}:/tmp/templatepg.dump\"
      sudo docker exec \"\${DB_CID}\" sh -lc 'pg_restore --clean --if-exists --no-owner -U postgres -d templatepg /tmp/templatepg.dump'
    fi
    if [ -f ${REMOTE_ROOT}/qdrant.snapshot ]; then
      curl -fsS -X POST \
        'http://127.0.0.1:6333/collections/${RESTORE_QDRANT_COLLECTION}/snapshots/upload?priority=snapshot' \
        -F 'snapshot=@${REMOTE_ROOT}/qdrant.snapshot'
      until curl -fsS http://127.0.0.1:6333/collections/${RESTORE_QDRANT_COLLECTION} >/dev/null 2>&1; do sleep 2; done
    fi
    if [ -d ${REMOTE_ROOT}/restore/media-private ]; then
      sudo docker run --rm --network host --entrypoint /bin/sh \
        -v ${REMOTE_ROOT}/restore:/restore \
        minio/mc -lc '
          mc alias set local http://127.0.0.1:9000 minioadmin minioadmin >/dev/null &&
          mc mb --ignore-existing local/media-private >/dev/null &&
          mc mirror --overwrite /restore/media-private local/media-private
        '
    fi
    \$COMPOSE_CMD up -d --build backend scheduler worker-sync worker-index worker-enrich worker-clips bot frontend nginx caddy
  "

echo "Deployed to https://${PUBLIC_HOSTNAME}"

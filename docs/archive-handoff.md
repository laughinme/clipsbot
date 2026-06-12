# ClipsBot Archive Handoff

This document is the handoff checklist for running ClipsBot with the restored
Telegram archive corpus on another machine.

## What To Send

Send the recipient:

1. The code repository:
   `https://github.com/laughinme/clipsbot`
2. The archive state files:
   - `templatepg_test.dump`
   - `knowledge_corpus_restored_http.snapshot`
   - `clipsbot-media-private.tar`
3. This document.

Do not send real `.env` files, Telegram bot tokens, Google credentials, JWT
private keys, or any other secrets.

## Current Archive State Location

The latest checked archive state is stored in this private GCS folder:

```bash
gs://project-e5159f37-a786-495c-a11-clipsbot-archive-staging/archive-state/
```

Expected objects:

```text
clipsbot-media-private.tar                 5.4 GB
knowledge_corpus_restored_http.snapshot    886 MB
templatepg_test.dump                       25 MB
```

The same Qdrant snapshot also exists in Google Drive:

```text
Google Drive / My Drive / AyuGram Desktop /
knowledge_corpus_restored_http-7104418264553038-2026-04-06-18-11-24.snapshot
```

Note: the Google Drive file may be cloud-only on macOS until explicitly
downloaded.

## Download The State Bundle

If the recipient has access to the GCP project or bucket:

```bash
mkdir -p archive-state
gcloud storage cp -r \
  gs://project-e5159f37-a786-495c-a11-clipsbot-archive-staging/archive-state/* \
  archive-state/
```

If sharing through Google Drive instead, put these files into a local
`archive-state/` folder at the repo root:

```text
archive-state/
  clipsbot-media-private.tar
  knowledge_corpus_restored_http.snapshot
  templatepg_test.dump
```

## Local Restore

Prerequisites:

- Docker Desktop or Docker Engine
- Docker Compose v2
- `curl`

Clone and restore:

```bash
git clone https://github.com/laughinme/clipsbot.git
cd clipsbot

# Put/download the three state files into ./archive-state first.
bash ops/archive/restore_state_bundle.sh ./archive-state
```

The script restores:

- Postgres metadata from `templatepg_test.dump`
- Qdrant vectors from `knowledge_corpus_restored_http.snapshot`
- MinIO archive media from `clipsbot-media-private.tar`

Then it starts the app through Docker Compose.

## Environment Notes

The restored corpus uses this Qdrant collection:

```bash
QDRANT_COLLECTION=knowledge_corpus_restored_http
```

Search quality depends on the query embedding provider matching the indexed
vectors. For real search, configure Google Vertex embeddings:

```bash
EMBEDDING_PROVIDER=vertex
GOOGLE_CLOUD_PROJECT=<project-id>
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/google/application_default_credentials.json
GOOGLE_APPLICATION_CREDENTIALS_HOST=/absolute/path/to/google-credentials.json
```

Without Google credentials the app can still start with the stub provider, but
semantic archive search will not match the existing Vertex-generated vectors
correctly.

## Smoke Test

After restore:

```bash
curl -s http://localhost/api/v1/archive/sources

curl -s -X POST http://localhost/api/v1/archive/search \
  -H 'content-type: application/json' \
  --data '{"query":"привет","limit":2,"offset":0,"filters":{"content_types":["text"]}}'
```

Expected result:

- `/archive/sources` returns the `Telegram Restored Local` source.
- `/archive/search` returns archive items for the query.

The UI should be available at:

```text
http://localhost/archive
```

## Prompt For Another Agent

If another developer uses an AI coding agent, send this prompt:

```text
Clone https://github.com/laughinme/clipsbot, read docs/archive-handoff.md,
download or place the three archive-state files into ./archive-state, then run
bash ops/archive/restore_state_bundle.sh ./archive-state. Do not commit or print
any real .env secrets. After restore, verify GET /api/v1/archive/sources and
POST /api/v1/archive/search with query "привет" return HTTP 200.
```

## Deploy To A VM

For a fresh Google Compute Engine VM, upload the state files and run the existing
deploy script from the repo owner machine:

```bash
PG_DUMP_PATH=/path/to/archive-state/templatepg_test.dump \
QDRANT_SNAPSHOT_PATH=/path/to/archive-state/knowledge_corpus_restored_http.snapshot \
MINIO_MEDIA_DIR=/path/to/unpacked/media-private \
RESTORE_QDRANT_COLLECTION=knowledge_corpus_restored_http \
ops/gcp/deploy_vm.sh
```

The current verified VM has these files already staged under `/srv/clipsbot/`.

## Verified State

On June 12, 2026, the running GCP VM was smoke-tested successfully:

- `GET /api/v1/archive/sources` returned HTTP 200.
- `POST /api/v1/archive/search` for `привет` returned HTTP 200 with archive
  results.
- `GET /archive` returned HTTP 200.

Verified URL at that time:

```text
https://34.57.224.214.sslip.io/archive
```

If the VM is stopped and restarted, the external IP can change. In that case,
update `PUBLIC_HOSTNAME`, `SITE_URL`, `WEBAPP_URL`, and
`STORAGE_ENDPOINT_PUBLIC` to `<new-ip>.sslip.io`, then recreate `caddy`,
`nginx`, `frontend`, and `backend`.

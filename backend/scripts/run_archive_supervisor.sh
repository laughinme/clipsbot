#!/bin/zsh
set -euo pipefail

SYNC_RUN_ID="${1:-3128fa65-3c4e-4976-a476-3263a306f054}"
export ARCHIVE_SYNC_RUN_ID="${SYNC_RUN_ID}"

cd "$(cd "$(dirname "$0")/.." && pwd)"
exec poetry run python scripts/launch_archive_supervisor.py

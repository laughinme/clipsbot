#!/bin/zsh
set -euo pipefail

PID_FILE="${ARCHIVE_SUPERVISOR_PID_FILE:-/tmp/archive-supervisor.pid}"

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    sleep 1
    kill -9 "${pid}" 2>/dev/null || true
    echo "archive supervisor stopped: pid=${pid}"
  else
    echo "archive supervisor not running"
  fi
  rm -f "${PID_FILE}"
else
  echo "archive supervisor pid file not found"
fi

pkill -f 'scripts/archive_supervisor.py' 2>/dev/null || true
pkill -f 'caffeinate -dimsu.*archive_supervisor.py' 2>/dev/null || true

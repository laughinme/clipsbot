#!/bin/zsh
set -euo pipefail

PID_FILE="${ARCHIVE_SUPERVISOR_PID_FILE:-/tmp/archive-supervisor.pid}"
LOG_FILE="${ARCHIVE_SUPERVISOR_LOG_FILE:-/tmp/archive-supervisor.log}"

if [[ -f "${PID_FILE}" ]]; then
  pid="$(cat "${PID_FILE}")"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    echo "archive supervisor running: pid=${pid}"
    ps -p "${pid}" -o pid,ppid,%cpu,%mem,rss,etime,stat,command
  else
    echo "archive supervisor pid file exists, but process is not running"
  fi
else
  echo "archive supervisor not running"
fi

if [[ -f "${LOG_FILE}" ]]; then
  echo "--- last log lines ---"
  tail -n 20 "${LOG_FILE}" || true
fi

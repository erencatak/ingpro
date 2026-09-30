#!/usr/bin/env bash
# Stops whatever start.sh started: the backend (8765) and the Vite dev server (5173).
set -uo pipefail
cd "$(dirname "$0")/.."

for entry in "8765 Backend" "5173 Web"; do
  set -- $entry
  port="$1"; name="$2"
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill 2>/dev/null
    echo "$name durduruldu (port $port)."
  else
    echo "$name zaten kapalı (port $port)."
  fi
done

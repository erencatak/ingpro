#!/usr/bin/env bash
# Runs the backend (port 8765) and the Vite dev server (port 5173) together. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
trap 'kill 0' EXIT
(cd server && uv run ingpro) &
(cd web && npm run dev) &
wait

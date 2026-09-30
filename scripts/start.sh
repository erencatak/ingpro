#!/usr/bin/env bash
# Starts the backend (8765) and the Vite dev server (5173) in the background and returns right away.
# Already running on that port? Left alone. Logs: data/backend.log, data/web.log. Stop with scripts/stop.sh.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p data

if lsof -ti:8765 >/dev/null 2>&1; then
  echo "Backend zaten çalışıyor (8765)."
else
  (cd server && nohup uv run ingpro > ../data/backend.log 2>&1 &)
  echo "Backend başlatıldı (8765), log: data/backend.log"
fi

if lsof -ti:5173 >/dev/null 2>&1; then
  echo "Web zaten çalışıyor (5173)."
else
  (cd web && nohup npm run dev > ../data/web.log 2>&1 &)
  echo "Web başlatıldı (5173), log: data/web.log"
fi

printf "Backend sağlık kontrolü bekleniyor"
ok=0
for _ in $(seq 1 30); do
  if curl -sf localhost:8765/api/health >/dev/null 2>&1; then
    ok=1
    break
  fi
  printf "."
  sleep 1
done
echo

if [ "$ok" = "1" ]; then
  echo "Backend hazır:  http://localhost:8765"
else
  echo "Backend henüz cevap vermiyor — data/backend.log dosyasına bak."
fi
echo "Web:            http://localhost:5173"

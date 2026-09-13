#!/usr/bin/env bash
# Serve the shed-plan browser locally. Usage: ./serve.sh [port]
set -euo pipefail
PORT="${1:-8787}"
cd "$(dirname "$0")"

if command -v lsof >/dev/null 2>&1 && lsof -ti "tcp:$PORT" >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Stop it with:  kill \$(lsof -ti tcp:$PORT)"
  echo "…or pick another port:  ./serve.sh 8080"
  exit 1
fi

echo "Woodshed → http://localhost:$PORT"
echo "Ctrl-C to stop."
exec python3 -m http.server "$PORT" --bind 127.0.0.1

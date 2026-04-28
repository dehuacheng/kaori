#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

pkill -f "uvicorn kaori.main:app" || true
sleep 1

export KAORI_VAULT_SYNC_ENABLED=true

mkdir -p logs
nohup .venv/bin/uvicorn kaori.main:app --host 0.0.0.0 --port 8000 \
  > logs/kaori.log 2>&1 &

echo "kaori restarted (pid $!), logs: $(pwd)/logs/kaori.log"

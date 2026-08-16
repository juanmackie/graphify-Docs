#!/usr/bin/env bash
# DocGraph — single-command local run (bash / Git Bash / WSL / macOS / Linux)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "→ Setting up backend..."
if [ ! -d "$ROOT/backend/.venv" ]; then
  (cd "$ROOT/backend" && uv venv .venv && uv pip install -r requirements.txt)
fi

echo "→ Setting up frontend..."
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  (cd "$ROOT/frontend" && npm install --no-audit --no-fund)
fi
if [ ! -d "$ROOT/frontend/dist" ]; then
  (cd "$ROOT/frontend" && npm run build)
fi

PY="$ROOT/backend/.venv/bin/python"
[ -x "$ROOT/backend/.venv/Scripts/python.exe" ] && PY="$ROOT/backend/.venv/Scripts/python.exe"

echo "→ Starting server on http://localhost:${PORT:-8000}"
(cd "$ROOT/backend" && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}")

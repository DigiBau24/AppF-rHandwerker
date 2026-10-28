#!/usr/bin/env bash
# Richtet Backend (venv) und Frontend (Next.js in ./web) lokal ein.
# Voraussetzungen: Python 3.12+, Node.js 20+ (inkl. npm)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Backend"
cd "$ROOT/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -r requirements-dev.txt
[ -f .env ] || cp .env.example .env
python -m pytest -q || true

echo "==> Frontend"
cd "$ROOT/web"
npm install
[ -f .env.local ] || cp .env.local.example .env.local

cat <<MSG

Fertig. Jetzt noch:
  1. supabase/schema.sql im Supabase SQL-Editor ausführen
  2. backend/.env und web/.env.local ausfüllen
  3. Terminal A:  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
     Terminal B:  cd web && npm run dev
  4. http://localhost:3000 öffnen
MSG

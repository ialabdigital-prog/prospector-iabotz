#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ e obrigatorio. Instale-o antes de continuar." >&2
  exit 1
fi

if [ ! -d venv ]; then
  python3 -m venv venv
fi

venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
venv/bin/playwright install chromium

mkdir -p sites drafts logs
touch sites/.gitkeep

if [ ! -f prospector-config.json ]; then
  cp prospector-config.example.json prospector-config.json
  echo "Criado prospector-config.json. Preencha as credenciais locais antes de iniciar."
fi

venv/bin/python - <<'PY'
from app.db import init_db
init_db()
print("Banco SQLite inicializado.")
PY

chmod +x prospector iniciar-dashboard.sh scripts/deploy-panel.sh

echo
echo "Instalacao concluida."
echo "1. Configure prospector-config.json e as variaveis PROSPECTOR_ADMIN_USER/PROSPECTOR_ADMIN_PASS."
echo "2. Execute ./iniciar-dashboard.sh."
echo "3. Abra http://127.0.0.1:8765."

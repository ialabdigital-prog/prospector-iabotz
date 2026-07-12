#!/bin/bash
# Iniciar Dashboard Prospector - Linux/Mac

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_SCRIPT="$BASE_DIR/skills/dashboard-leads/references/dashboard-server.py"
DB_FILE="$BASE_DIR/prospector.db"

echo "🚀 Iniciando Prospector Dashboard..."

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 não encontrado. Instale: apt install python3 / brew install python3"
    exit 1
fi

# Verificar script do servidor
if [ ! -f "$SERVER_SCRIPT" ]; then
    echo "❌ Script do servidor não encontrado: $SERVER_SCRIPT"
    echo "   Rode /setup primeiro para copiar os arquivos."
    exit 1
fi

# Inicializar banco se não existe
if [ ! -f "$DB_FILE" ]; then
    echo "📦 Criando banco de dados..."
    python3 -c "
import sqlite3
conn = sqlite3.connect('$DB_FILE')
conn.executescript('''
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
  email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
  status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
  contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT, endCliente TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime')));
''')
conn.commit()
print('✅ Banco criado:', '$DB_FILE')
"
fi

# Gerar dashboard.html inicial se não existe
DASHBOARD_HTML="$BASE_DIR/dashboard.html"
if [ ! -f "$DASHBOARD_HTML" ]; then
    echo "📄 Gerando dashboard.html inicial..."
    python3 "$SERVER_SCRIPT" --generate-only
fi

echo ""
echo "✅ Dashboard disponível em: http://localhost:8765"
echo "   Pressione Ctrl+C para parar"
echo ""

# Iniciar servidor
cd "$BASE_DIR"
exec python3 "$SERVER_SCRIPT"
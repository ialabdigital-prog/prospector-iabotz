#!/usr/bin/env bash
# ============================================================
# INSTALAÇÃO PROSPECTOR IA BOTZ
# Configura ambiente completo no servidor local
# ============================================================

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       🤖 INSTALAÇÃO PROSPECTOR IA BOTZ v0.14.0             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 1. Python & pip
echo "📦 Verificando Python..."
if ! command -v python3 &> /dev/null; then
    echo "   Instalando Python3..."
    apt-get update && apt-get install -y python3 python3-pip python3-venv
fi
python3 --version

# 2. Virtual Environment
echo ""
echo "🐍 Criando virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 3. Dependências Python
echo ""
echo "📚 Instalando dependências Python..."
pip install --upgrade pip
pip install -r requirements.txt 2>/dev/null || pip install \
    playwright \
    paramiko \
    requests \
    playwright-stealth \
    aiohttp \
    beautifulsoup4 \
    lxml

# 4. Playwright browsers
echo ""
echo "🌐 Instalando Playwright Chromium..."
playwright install chromium
playwright install-deps chromium 2>/dev/null || true

# 5. Tornar scripts executáveis
echo ""
echo "🔧 Configurando permissões..."
chmod +x prospector
chmod +x iniciar-dashboard.sh
chmod +x skills/prospeccao-playwright/references/scraper-playwright.py
chmod +x skills/deploy-aapanel/references/aapanel-api.py

# 6. Criar estrutura de pastas
echo ""
echo "📁 Criando estrutura de pastas..."
mkdir -p sites
mkdir -p logs

# 7. Verificar/Criar config
echo ""
echo "⚙️  Verificando configuração..."
if [ ! -f "prospector-config.json" ]; then
    echo "   Configuração não encontrada. Será criada no primeiro setup."
else
    echo "   ✅ prospector-config.json encontrado"
fi

# 8. Dashboard server
echo ""
echo "📊 Configurando Dashboard..."
if [ ! -f "dashboard-server.py" ]; then
    cat > dashboard-server.py << 'DASHBOARD_EOF'
#!/usr/bin/env python3
"""
Dashboard Server - Prospector IA Botz
Servidor local para painel de controle (SQLite + HTML)
"""

import sqlite3
import json
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

BASE_DIR = Path(__file__).parent
DB_FILE = BASE_DIR / "prospector.db"
DASHBOARD_FILE = BASE_DIR / "dashboard.html"
TEMPLATE_FILE = BASE_DIR / "skills" / "dashboard-leads" / "references" / "dashboard-template.html"
PORT = 8765

# Schema do banco (skill dashboard-leads)
SCHEMA = """
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
  email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
  status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
  contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT, endCliente TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime'))
);
"""

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"✅ Banco inicializado: {DB_FILE}")

def get_leads():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY atualizado DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def upsert_lead(lead: dict):
    conn = sqlite3.connect(DB_FILE)
    cols = ', '.join(lead.keys())
    placeholders = ', '.join(['?' for _ in lead])
    updates = ', '.join([f"{k}=excluded.{k}" for k in lead.keys() if k != 'slug'])
    sql = f"INSERT INTO leads ({cols}) VALUES ({placeholders}) ON CONFLICT(slug) DO UPDATE SET {updates}, atualizado=datetime('now','localtime')"
    conn.execute(sql, tuple(lead.values()))
    conn.commit()
    conn.close()

class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/leads':
            self.send_json(get_leads())
        elif parsed.path == '/api/stats':
            leads = get_leads()
            stats = {
                'total': len(leads),
                'novo': len([l for l in leads if l['status']=='novo']),
                'redesenhado': len([l for l in leads if l['status']=='redesenhado']),
                'publicado': len([l for l in leads if l['status']=='publicado']),
                'proposta': len([l for l in leads if l['status']=='proposta enviada']),
                'descartado': len([l for l in leads if l['status']=='descartado']),
                'receita': sum(l.get('valor',0) or 0 for l in leads if l['status']=='fechado'),
            }
            self.send_json(stats)
        elif parsed.path == '/':
            # Servir dashboard.html se existir, senão gerar
            if DASHBOARD_FILE.exists():
                self.path = '/dashboard.html'
                return super().do_GET()
            else:
                self.send_html("<h1>Dashboard não gerado. Rode o setup ou /prospectar primeiro.</h1>")
        else:
            return super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        if parsed.path == '/api/leads/upsert':
            upsert_lead(data)
            self.send_json({'success': True, 'slug': data.get('slug')})
        elif parsed.path == '/api/leads/delete':
            slug = data.get('slug')
            conn = sqlite3.connect(DB_FILE)
            conn.execute("DELETE FROM leads WHERE slug=?", (slug,))
            conn.commit()
            conn.close()
            self.send_json({'success': True})
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # Silenciar logs

def regenerate_dashboard():
    """Regenera dashboard.html do template com dados atuais"""
    leads = get_leads()
    snapshot = {
        'atualizado': time.strftime('%Y-%m-%d %H:%M:%S'),
        'leads': leads
    }
    
    if TEMPLATE_FILE.exists():
        template = TEMPLATE_FILE.read_text(encoding='utf-8')
    else:
        # Template mínimo embutido
        template = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Prospector Dashboard</title>
<style>body{font-family:system-ui;margin:20px}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:8px;text-align:left}th{background:#f5f5f5}</style>
</head><body>
<h1>📊 Prospector Dashboard</h1>
<p>Atualizado: __ATUALIZADO__</p>
<table><thead><tr><th>Slug</th><th>Nome</th><th>Status</th><th>URL</th><th>Ações</th></tr></thead>
<tbody id="tbody"></tbody></table>
<script>
const data = __DADOS__;
const tbody = document.getElementById('tbody');
data.leads.forEach(l => {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${l.slug}</td><td>${l.nome}</td><td>${l.status}</td><td><a href="${l.urlNova}" target="_blank">${l.urlNova || '-'}</a></td><td><button onclick="del('${l.slug}')">Excluir</button></td>`;
  tbody.appendChild(tr);
});
function del(slug){ if(confirm('Excluir '+slug+'?')) fetch('/api/leads/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slug})}).then(()=>location.reload()); }
</script>
</body></html>'''
    
    html = template.replace('__DADOS__', json.dumps(snapshot, ensure_ascii=False)).replace('__ATUALIZADO__', snapshot['atualizado'])
    DASHBOARD_FILE.write_text(html, encoding='utf-8')
    print(f"✅ Dashboard regenerado: {DASHBOARD_FILE}")

def main():
    init_db()
    regenerate_dashboard()
    
    print(f"🚀 Iniciando Dashboard Server em http://localhost:{PORT}")
    print(f"   Banco: {DB_FILE}")
    print(f"   Dashboard: {DASHBOARD_FILE}")
    print("   Pressione Ctrl+C para parar")
    
    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor parado")
        server.shutdown()

if __name__ == '__main__':
    main()
DASHBOARD_EOF
fi

chmod +x dashboard-server.py

# 9. Script iniciar-dashboard.sh
if [ ! -f "iniciar-dashboard.sh" ]; then
    cat > iniciar-dashboard.sh << 'DASH_SH_EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true
echo "🚀 Iniciando Prospector Dashboard..."
echo "   Acesse: http://localhost:8765"
echo "   Pressione Ctrl+C para parar"
python3 dashboard-server.py
DASH_SH_EOF
    chmod +x iniciar-dashboard.sh
fi

# 10. requirements.txt
cat > requirements.txt << 'REQ_EOF'
playwright>=1.40.0
playwright-stealth>=1.0.0
paramiko>=3.0.0
requests>=2.31.0
aiohttp>=3.9.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
REQ_EOF

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ INSTALAÇÃO CONCLUÍDA!                                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Próximos passos:"
echo "  1. ./prospector setup     # Configuração guiada (assinatura, aapanel, etc.)"
echo "  2. ./prospector           # Menu interativo principal"
echo ""
echo "Comandos diretos:"
echo "  ./prospector prospectar           # Prospecção Playwright"
echo "  ./prospector redesenhar           # Redesign sites"
echo "  ./prospector publicar             # Deploy aapanel"
echo "  ./prospector proposta             # Enviar propostas"
echo "  ./prospector dashboard            # Dashboard local"
echo ""
echo "Dashboard: ./iniciar-dashboard.sh  (abre http://localhost:8765)"
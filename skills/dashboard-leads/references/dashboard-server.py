#!/usr/bin/env python3
"""
Dashboard Server - Mini servidor local para o Prospector Dashboard
Roda na porta 8765, serve dashboard.html com dados do SQLite
Requer apenas Python padrão (sem dependências externas)
"""

import http.server
import json
import sqlite3
import os
import sys
import argparse
from pathlib import Path
from urllib.parse import urlparse
import mimetypes

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).parent.parent.parent.parent
DB_FILE = BASE_DIR / 'prospector.db'
DASHBOARD_TEMPLATE = BASE_DIR / 'skills' / 'dashboard-leads' / 'references' / 'dashboard-template.html'
DASHBOARD_HTML = BASE_DIR / 'dashboard.html'
PORT = 8765
HOST = '0.0.0.0'

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
  email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
  status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
  contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT, endCliente TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime')));
"""

# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def get_all_leads():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM leads 
            ORDER BY CASE status 
                WHEN 'novo' THEN 0 WHEN 'redesenhado' THEN 1 WHEN 'publicado' THEN 2 
                WHEN 'proposta' THEN 3 WHEN 'respondeu' THEN 4 WHEN 'fechado' THEN 5 
                WHEN 'descartado' THEN 6 ELSE 99 END, 
                atualizado DESC
        """).fetchall()
    return [dict(r) for r in rows]

def upsert_lead(lead: dict):
    cols = ['slug','nome','nicho','cidade','nota','avaliacoes','email','telefone','whatsapp','siteAntigo','motivo','status','urlNova','dataProposta','valor','obs','contratoStatus','contratoEm','manutencao','pago','docCliente','endCliente','atualizado']
    vals = [lead.get(c) for c in cols]
    placeholders = ','.join(['?']*len(cols))
    updates = ','.join([f'{c}=excluded.{c}' for c in cols if c != 'slug'])
    sql = f"INSERT INTO leads ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(slug) DO UPDATE SET {updates}, atualizado=datetime('now','localtime')"
    with get_db() as conn:
        conn.execute(sql, vals)
        conn.commit()

def delete_lead(slug: str):
    with get_db() as conn:
        conn.execute("DELETE FROM leads WHERE slug=?", (slug,))
        conn.commit()

# ============================================================
# DASHBOARD HTML GENERATION
# ============================================================

def generate_dashboard_html():
    """Gera dashboard.html a partir do template com dados embutidos"""
    if not DASHBOARD_TEMPLATE.exists():
        print(f"Template não encontrado: {DASHBOARD_TEMPLATE}")
        return False
    
    leads = get_all_leads()
    snapshot = {
        'atualizado': __import__('datetime').datetime.now().isoformat(),
        'leads': leads
    }
    
    template = DASHBOARD_TEMPLATE.read_text(encoding='utf-8')
    html = template.replace('__DADOS__', json.dumps(snapshot, ensure_ascii=False))
    DASHBOARD_HTML.write_text(html, encoding='utf-8')
    print(f"✅ dashboard.html gerado com {len(leads)} leads")
    return True

# ============================================================
# HTTP HANDLER
# ============================================================

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API endpoints
        if path == '/api/leads':
            self.send_json(get_all_leads())
            return
        if path == '/api/stats':
            leads = get_all_leads()
            self.send_json(calc_stats(leads))
            return
        if path == '/api/health':
            self.send_json({'status':'ok','mode':'server'})
            return
        
        # Dashboard principal - regenerar com dados atuais
        if path in ('/', '/dashboard', '/dashboard.html'):
            generate_dashboard_html()
            self.serve_file(DASHBOARD_HTML, 'text/html')
            return
        
        # Arquivos estáticos
        self.serve_static(path)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/leads':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                lead = json.loads(body)
                if not lead.get('slug'):
                    self.send_error(400, 'slug obrigatório')
                    return
                upsert_lead(lead)
                generate_dashboard_html()
                self.send_json({'success': True, 'slug': lead['slug']})
            except json.JSONDecodeError:
                self.send_error(400, 'JSON inválido')
            return
        self.send_error(404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/leads/'):
            slug = parsed.path.split('/')[-1]
            delete_lead(slug)
            generate_dashboard_html()
            self.send_json({'success': True})
            return
        self.send_error(404)
    
    def calc_stats(self, leads):
        stats = {s:0 for s in ['novo','redesenhado','publicado','proposta','respondeu','fechado','descartado']}
        valor_total = 0
        mrr = 0
        for l in leads:
            if l['status'] in stats:
                stats[l['status']] += 1
            if l.get('valor'):
                valor_total += float(l['valor'])
            if l.get('manutencao'):
                mrr += float(l['manutencao'])
        return {'total': len(leads), **stats, 'valor_total': valor_total, 'mrr': mrr}
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def serve_file(self, filepath, content_type):
        try:
            content = filepath.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)
    
    def serve_static(self, path):
        # Segurança: só serve arquivos dentro de BASE_DIR
        try:
            filepath = (BASE_DIR / path.lstrip('/')).resolve()
            if not str(filepath).startswith(str(BASE_DIR.resolve())):
                self.send_error(403)
                return
            
            if filepath.is_file():
                mime = mimetypes.guess_type(str(filepath))[0] or 'application/octet-stream'
                self.serve_file(filepath, mime)
            else:
                self.send_error(404)
        except Exception:
            self.send_error(404)
    
    def log_message(self, format, *args):
        # Silenciar logs de requisições normais
        if '/api/' not in format % args:
            return
        super().log_message(format, *args)

# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Prospector Dashboard Server')
    parser.add_argument('--port', type=int, default=PORT, help=f'Porta (padrão: {PORT})')
    parser.add_argument('--host', default=HOST, help=f'Host (padrão: {HOST})')
    parser.add_argument('--generate-only', action='store_true', help='Só gerar dashboard.html e sair')
    args = parser.parse_args()
    
    init_db()
    
    if args.generate_only:
        generate_dashboard_html()
        return
    
    print(f"🚀 Prospector Dashboard Server")
    print(f"   http://{args.host}:{args.port}")
    print(f"   Banco: {DB_FILE}")
    print(f"   Pressione Ctrl+C para parar")
    
    server = http.server.HTTPServer((args.host, args.port), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor parado")

if __name__ == '__main__':
    main()
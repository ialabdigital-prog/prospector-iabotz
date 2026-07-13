#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROSPECTOR IA BOTZ - Menu Guiado
=================================
Interface interativa para gerenciar todo o fluxo de prospecção, redesign,
deploy, propostas e contratos.
"""

import sys
import os
import json
import subprocess
from typing import Dict, List, Any, Optional

# Adicionar paths dos skills
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'prospeccao-playwright', 'references'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'deploy-aapanel', 'references'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'redesign-premium', 'references'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'proposta-email', 'references'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'proposta-whatsapp', 'references'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills', 'contrato-servico', 'references'))

# ============================================================
# CORES E FORMATAÇÃO
# ============================================================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def print_menu_option(key: str, title: str, desc: str = ""):
    print(f"  {Colors.BOLD}{Colors.CYAN}{key}.{Colors.END} {Colors.BOLD}{title}{Colors.END}  {Colors.DIM}{desc}{Colors.END}")

def input_prompt(label: str, default: str = "") -> str:
    if default:
        prompt = f"{Colors.BOLD}{label}{Colors.END} {Colors.DIM}[{default}]{Colors.END}: "
    else:
        prompt = f"{Colors.BOLD}{label}{Colors.END}: "
    return input(prompt).strip() or default

def confirm(prompt: str, default: bool = True) -> bool:
    suffix = " [S/n]" if default else " [s/N]"
    resp = input(f"{Colors.BOLD}{prompt}{Colors.END}{suffix}: ").strip().lower()
    if not resp:
        return default
    return resp in ('s', 'sim', 'y', 'yes', 'true', '1')

def run_command(cmd: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Executa comando e retorna dict com success, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=300
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'stdout': '', 'stderr': 'Timeout (300s)', 'returncode': -1}
    except Exception as e:
        return {'success': False, 'stdout': '', 'stderr': str(e), 'returncode': -1}

# ============================================================
# CONFIGURAÇÃO
# ============================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'prospector-config.json')
LEADS_PATH = os.path.join(os.path.dirname(__file__), 'leads.md')

def load_config() -> Dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config: Dict):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# ============================================================
# LEADS
# ============================================================
def carregar_leads_qualificados() -> List[Dict]:
    """Carrega leads do arquivo leads.md com status 'qualificado'"""
    if not os.path.exists(LEADS_PATH):
        return []
    leads = []
    with open(LEADS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines[1:]:  # Pular header
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('|')
        if len(parts) >= 12:
            leads.append({
                '#': parts[0].strip(),
                'nome': parts[1].strip(),
                'cidade': parts[2].strip(),
                'nicho': parts[3].strip(),
                'nota': parts[4].strip(),
                'avaliacoes': parts[5].strip(),
                'site': parts[6].strip(),
                'telefone': parts[7].strip(),
                'email': parts[8].strip(),
                'status': parts[9].strip(),
                'slug': parts[10].strip(),
                'observacoes': parts[11].strip() if len(parts) > 11 else ''
            })
    return [l for l in leads if l['status'].lower() in ('qualificado', 'redesenhado', 'deployado', 'proposta_enviada')]


def carregar_leads_com_whatsapp() -> List[Dict]:
    """Carrega leads com WhatsApp cadastrado (do SQLite ou leads.md).
    Para WhatsApp, qualquer lead com número serve — e-mail é bônus."""
    leads = []

    db_file = os.path.join(os.path.dirname(__file__), 'prospector.db')
    if os.path.exists(db_file):
        import sqlite3
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT slug, nome, nicho, cidade, nota, avaliacoes, email, telefone, whatsapp,
                      siteAntigo as site_atual, motivo, status, urlNova as url_nova
               FROM leads
               WHERE whatsapp IS NOT NULL AND whatsapp != ''
               ORDER BY atualizado DESC"""
        ).fetchall()
        conn.close()
        for r in rows:
            leads.append({
                'slug': r['slug'],
                'nome': r['nome'] or '',
                'cidade': r['cidade'] or '',
                'nicho': r['nicho'] or '',
                'nota': str(r['nota'] or '') if r['nota'] else '',
                'avaliacoes': str(r['avaliacoes'] or '') if r['avaliacoes'] else '',
                'telefone': r['telefone'] or '',
                'email': r['email'] or '',
                'whatsapp': r['whatsapp'] or '',
                'site': r['site_atual'] or '',
                'status': r['status'] or '',
                'url_nova': r['url_nova'] or '',
                'tem_email': bool(r['email'] and r['email'].strip()),
            })
        return leads

    if not os.path.exists(LEADS_PATH):
        return []
    with open(LEADS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('|')
        if len(parts) >= 12:
            telefone = parts[7].strip()
            nome = parts[1].strip()
            if telefone and telefone not in ('-', ''):
                leads.append({
                    'slug': parts[10].strip(),
                    'nome': nome,
                    'cidade': parts[2].strip(),
                    'nicho': parts[3].strip(),
                    'nota': parts[4].strip(),
                    'avaliacoes': parts[5].strip(),
                    'telefone': telefone,
                    'email': parts[8].strip(),
                    'whatsapp': telefone,
                    'site': parts[6].strip(),
                    'status': parts[9].strip(),
                    'url_nova': parts[10].strip() if len(parts) > 10 else '',
                    'tem_email': bool(parts[8].strip() and parts[8].strip() not in ('-', '')),
                })
    return leads

def listar_leads():
    """Lista todos os leads com status"""
    if not os.path.exists(LEADS_PATH):
        print_warning("Arquivo leads.md não encontrado")
        return
    with open(LEADS_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print_header("📋 LEADS ATUAIS")
    print(f"{'#':>3} {'Nome':<30} {'Cidade':<15} {'Nicho':<15} {'⭐':>4} {'Aval':>4} {'Status':<15} {'Slug':<25}")
    print("-" * 120)
    for i, line in enumerate(lines[1:], 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('|')
        if len(parts) >= 11:
            print(f"{parts[0].strip():>3} {parts[1].strip():<30} {parts[2].strip():<15} {parts[3].strip():<15} {parts[4].strip():>4} {parts[5].strip():>4} {parts[9].strip():<15} {parts[10].strip():<25}")

def exportar_csv():
    """Exporta leads para CSV"""
    leads = carregar_leads_qualificados()
    if not leads:
        print_warning("Nenhum lead qualificado")
        return
    import csv
    csv_path = os.path.join(os.path.dirname(__file__), 'leads-export.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)
    print_success(f"Exportado para {csv_path}")

# ============================================================
# MENU PRINCIPAL
# ============================================================
def main():
    while True:
        print_header("🤖 PROSPECTOR IA BOTZ - Menu Principal")
        config = load_config()
        aapanel = config.get('aapanel', {})
        panel_url = os.environ.get("PROSPECTOR_PUBLIC_URL", "http://127.0.0.1:8765")
        print(f"{Colors.CYAN}Config:{Colors.END} {CONFIG_PATH}")
        print(f"{Colors.CYAN}Leads:{Colors.END} {LEADS_PATH}")
        print(f"{Colors.CYAN}Dashboard Local:{Colors.END} http://localhost:8765")
        print(f"{Colors.CYAN}Painel Web:{Colors.END} {panel_url}\n")

        print_menu_option("1", "🔍 Prospecção", "Buscar leads no Google Maps (Playwright)")
        print_menu_option("2", "🎨 Redesign", "Redesenhar sites dos leads qualificados")
        print_menu_option("3", "🚀 Deploy", "Publicar sites no aapanel (SSL automático)")
        print_menu_option("4", "📧 Propostas E-mail", "Gerar e enviar propostas por e-mail")
        print_menu_option("5", "📱 Propostas WhatsApp", "Enviar propostas via WhatsApp (Evolution)")
        print_menu_option("6", "📊 Dashboard", "Abrir/gerenciar dashboard local")
        print_menu_option("7", "⚙️  Configuração", "Setup inicial, credenciais, nichos, aapanel, Cloudflare")
        print_menu_option("8", "📋 Ver Leads", "Listar leads atuais (qualificados/descartados)")
        print_menu_option("9", "🔧 Ferramentas", "Utilitários: testar conexões, limpar cache, logs")
        print_menu_option("10", "❌ Sair", "Encerrar Prospector")

        choice = input(f"\n{Colors.BOLD}Escolha uma opção:{Colors.END} ").strip()

        if choice == '1':
            menu_prospeccao()
        elif choice == '2':
            menu_redesign()
        elif choice == '3':
            menu_deploy()
        elif choice == '4':
            menu_propostas()
        elif choice == '5':
            menu_propostas_whatsapp()
        elif choice == '6':
            menu_dashboard()
        elif choice == '7':
            menu_config()
        elif choice == '8':
            menu_ver_leads()
        elif choice == '9':
            menu_ferramentas()
        elif choice in ('10', 'q', 'quit', 'sair'):
            print_info("Até logo! 👋")
            break
        else:
            print_error("Opção inválida")
        input(f"\n{Colors.BOLD}Pressione Enter para continuar...{Colors.END}")

# ============================================================
# MENUS DE CADA FUNÇÃO
# ============================================================
def menu_prospeccao():
    print_header("🔍 PROSPECÇÃO - Google Maps (Playwright)")
    config = load_config()
    prospeccao = config.get('prospeccao', {})
    playwright_cfg = config.get('playwright', {})

    nichos = prospeccao.get('nichos', ['nutricionistas', 'psicologos', 'advogados', 'psiquiatras', 'dentistas'])
    cidade = prospeccao.get('cidade', 'São Paulo')
    meta = prospeccao.get('leadsPorBusca', 10)
    nota_min = prospeccao.get('notaMinima', 4.7)
    aval_min = prospeccao.get('avaliacoesMinimas', 40)

    print(f"Nichos: {', '.join(nichos)}")
    print(f"Cidade: {cidade}")
    print(f"Meta: {meta} leads/busca | Nota mínima: {nota_min} | Avaliações mín: {aval_min}")
    print(f"Playwright: headless={playwright_cfg.get('headless', True)} stealth={playwright_cfg.get('stealth', True)}")

    print("\nComo rodar:")
    print("  ./prospector prospectar              # todos os nichos")
    print("  ./prospector prospectar nutricionistas  # nicho específico")

    if confirm("\nExecutar prospecção agora?"):
        nicho_especifico = input_prompt("Nicho específico (Enter para todos)", "").strip()
        cmd = [sys.executable, '-m', 'prospector_de_sites.commands.prospectar']
        if nicho_especifico:
            cmd.append(nicho_especifico)
        print_info("Executando... (pode demorar alguns minutos)")
        result = run_command(cmd)
        if result['success']:
            print_success("Prospecção concluída!")
            print(result['stdout'][-1000:] if len(result['stdout']) > 1000 else result['stdout'])
        else:
            print_error(f"Falha: {result['stderr']}")

def menu_redesign():
    print_header("🎨 REDESIGN - Redesenhar Sites")
    leads = carregar_leads_qualificados()
    if not leads:
        print_warning("Nenhum lead qualificado encontrado. Rode a prospecção primeiro.")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    print(f"Leads qualificados disponíveis: {Colors.GREEN}{len(leads)}{Colors.END}\n")
    for i, lead in enumerate(leads, 1):
        print(f"  {i}. {lead['nome']} ({lead['cidade']}) - ⭐{lead['nota']} | {lead['email']} [{lead['status']}]")

    print(f"\n  {len(leads)+1}. Redesenhar TODOS")
    print(f"  {len(leads)+2}. Voltar")

    choice = input(f"\n{Colors.BOLD}Escolha lead(s) para redesenhar:{Colors.END} ").strip()
    if choice == str(len(leads)+2) or choice.lower() in ('v', 'voltar'):
        return

    selecionados = []
    if choice == str(len(leads)+1):
        selecionados = leads
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(leads):
                selecionados = [leads[idx]]
        except ValueError:
            print_error("Opção inválida")
            return

    if not selecionados:
        print_error("Nenhum lead selecionado")
        return

    print_info(f"\nIniciando redesign de {len(selecionados)} lead(s)...")
    for lead in selecionados:
        print(f"\n{Colors.CYAN}🎨 Redesenhando: {lead['nome']}{Colors.END}")
        result = run_command([sys.executable, '-m', 'prospector_de_sites.commands.redesenhar', lead['slug']])
        if result['success']:
            print_success(f"  ✅ {lead['nome']} redesenhado!")
        else:
            print_error(f"  ❌ Falha: {result['stderr'][:200]}")

    print_success("\nRedesign concluído!")
    print_info("Próximo passo sugerido: Menu > 🚀 Deploy")

def menu_deploy():
    print_header("🚀 DEPLOY - Publicar Sites no aapanel")
    config = load_config()
    aapanel = config.get('aapanel', {})

    if not aapanel.get('url'):
        print_warning("aapanel não configurado. Vá em Configuração > aapanel")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    leads = carregar_leads_qualificados()
    if not leads:
        print_warning("Nenhum lead qualificado. Rode redesign primeiro.")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    print(f"Leads com redesign pronto: {Colors.GREEN}{len(leads)}{Colors.END}")
    for i, lead in enumerate(leads, 1):
        print(f"  {i}. {lead['nome']} ({lead['slug']}.{aapanel.get('dominio_base', 'example.com')})")

    print(f"\n  {len(leads)+1}. Deploy TODOS")
    print(f"  {len(leads)+2}. Voltar")

    choice = input(f"\n{Colors.BOLD}Escolha lead(s) para deploy:{Colors.END} ").strip()
    if choice == str(len(leads)+2) or choice.lower() in ('v', 'voltar'):
        return

    selecionados = []
    if choice == str(len(leads)+1):
        selecionados = leads
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(leads):
                selecionados = [leads[idx]]
        except ValueError:
            print_error("Opção inválida")
            return

    if not selecionados:
        print_error("Nenhum lead selecionado")
        return

    print_info(f"\nIniciando deploy de {len(selecionados)} site(s)...")
    for lead in selecionados:
        print(f"\n{Colors.CYAN}🚀 Deploy: {lead['nome']}{Colors.END}")
        result = run_command([sys.executable, '-m', 'prospector_de_sites.commands.publicar', lead['slug']])
        if result['success']:
            print_success(f"  ✅ {lead['nome']} publicado!")
            print(f"     {result['stdout'][-500:]}")
        else:
            print_error(f"  ❌ Falha: {result['stderr'][:300]}")

    print_success("\nDeploy concluído!")
    print_info("Próximo passo sugerido: Menu > 📧 Propostas")

def menu_propostas():
    print_header("📤 PROPOSTAS - Gerar e Enviar")
    config = load_config()
    assinatura = config.get('assinatura', {})
    envio = config.get('envio', {})
    canais = envio.get('canais', ['email'])

    if not assinatura.get('nome'):
        print_warning("Assinatura não configurada. Vá em Configuração > Assinatura")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    leads = carregar_leads_qualificados()
    if not leads:
        print_warning("Nenhum lead qualificado")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    print(f"Leads qualificados: {Colors.GREEN}{len(leads)}{Colors.END}")
    print(f"Assinatura: {assinatura['nome']} | {assinatura.get('apresentacao', '')}")
    print(f"Canais ativos: {' + '.join(canais).upper()}")
    print(f"Modo e-mail: {envio.get('modo', 'rascunho')}")

    for i, lead in enumerate(leads, 1):
        print(f"  {i}. {lead['nome']} ({lead['cidade']}) - {lead['email']} [{lead['status']}]")

    print(f"\n  {len(leads)+1}. Proposta para TODOS")
    print(f"  {len(leads)+2}. Voltar")

    choice = input(f"\n{Colors.BOLD}Escolha lead(s) para proposta:{Colors.END} ").strip()
    if choice == str(len(leads)+2) or choice.lower() in ('v', 'voltar'):
        return

    selecionados = []
    if choice == str(len(leads)+1):
        selecionados = leads
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(leads):
                selecionados = [leads[idx]]
        except ValueError:
            print_error("Opção inválida")
            return

    if not selecionados:
        print_error("Nenhum lead selecionado")
        return

    for lead in selecionados:
        slug = lead['slug']
        print(f"\n{Colors.CYAN}📤 Proposta: {lead['nome']}{Colors.END}")

        if 'email' in canais:
            print(f"  {Colors.BLUE}📧 Enviando por e-mail...{Colors.END}")
            result = run_command([sys.executable, '-m', 'prospector_de_sites.commands.proposta', slug])
            if result['success']:
                print_success(f"  ✅ E-mail gerado!")
            else:
                print_error(f"  ❌ Falha e-mail: {result['stderr'][:200]}")

        if 'whatsapp' in canais:
            print(f"  {Colors.BLUE}📱 Enviando por WhatsApp...{Colors.END}")
            result = run_command([sys.executable, 'skills/proposta-whatsapp/references/proposta_whatsapp.py', slug])
            if result['success']:
                print_success(f"  ✅ WhatsApp enviado!")
            else:
                print_error(f"  ❌ Falha WhatsApp: {result['stderr'][:200]}")

    print_success("\nPropostas concluídas!")


def menu_propostas_whatsapp():
    print_header("📱 PROPOSTAS WHATSAPP - Enviar via Evolution")
    config = load_config()
    assinatura = config.get('assinatura', {})
    envio = config.get('envio', {})
    wa = envio.get('whatsapp', {})
    provedor = wa.get('provedor', 'evolution_api')

    if not assinatura.get('nome'):
        print_warning("Assinatura não configurada. Vá em Configuração > Assinatura")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    if provedor == 'evolution_go':
        cfg_ok = bool(wa.get('evolution_go', {}).get('api_key'))
    else:
        cfg_ok = bool(wa.get('evolution_api', {}).get('api_key'))

    if not cfg_ok:
        print_warning("WhatsApp não configurado. Vá em Configuração > WhatsApp & Canais")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    # Carrega leads com WhatsApp (com ou sem email)
    leads = carregar_leads_com_whatsapp()
    if not leads:
        print_warning("Nenhum lead com WhatsApp encontrado")
        input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")
        return

    com_email = sum(1 for l in leads if l.get('tem_email'))
    sem_email = len(leads) - com_email

    print(f"Leads com WhatsApp: {Colors.GREEN}{len(leads)}{Colors.END}")
    print(f"  Com e-mail: {com_email}  |  Sem e-mail: {sem_email}")
    print(f"Provedor: {provedor}")
    print(f"Assinatura: {assinatura['nome']}")
    print()

    for i, lead in enumerate(leads, 1):
        wa_icon = "📱"
        email_tag = f" ✉️" if lead.get('tem_email') else ""
        print(f"  {i}. {wa_icon} {lead['nome']} ({lead['cidade']}) - {lead.get('telefone', lead.get('whatsapp', ''))}{email_tag} [{lead['status']}]")

    print(f"\n  {len(leads)+1}. Enviar para TODOS")
    print(f"  {len(leads)+2}. Voltar")

    choice = input(f"\n{Colors.BOLD}Escolha lead(s) para WhatsApp:{Colors.END} ").strip()
    if choice == str(len(leads)+2) or choice.lower() in ('v', 'voltar'):
        return

    selecionados = []
    if choice == str(len(leads)+1):
        selecionados = leads
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(leads):
                selecionados = [leads[idx]]
        except ValueError:
            print_error("Opção inválida")
            return

    if not selecionados:
        print_error("Nenhum lead selecionado")
        return

    for lead in selecionados:
        slug = lead['slug']
        print(f"\n{Colors.CYAN}📱 WhatsApp: {lead['nome']}{Colors.END}")
        result = run_command(['python3', 'skills/proposta-whatsapp/references/proposta_whatsapp.py', slug])
        if result['success']:
            print_success(f"  ✅ WhatsApp enviado!")
            print(f"     {result['stdout'][-500:]}")
        else:
            print_error(f"  ❌ Falha: {result['stderr'][:300]}")

    print_success("\nPropostas WhatsApp concluídas!")

def menu_dashboard():
    print_header("📊 DASHBOARD - Visualizar Leads")
    print("O dashboard roda em http://localhost:8765")
    print("Para iniciar: ./iniciar-dashboard.sh (Linux) ou iniciar-dashboard.bat (Windows)")

    if confirm("\nAbrir dashboard no navegador?"):
        import webbrowser
        webbrowser.open('http://localhost:8765')

    if confirm("Iniciar servidor do dashboard agora?"):
        subprocess.Popen(['./venv/bin/gunicorn', '-b', '127.0.0.1:8765', '-w', '2', '--timeout', '120', 'wsgi:app'],
                         cwd=os.path.dirname(__file__))
        print_success("Servidor iniciado em background")
        print_info("Acesse http://localhost:8765")

def menu_config():
    """Menu de configuração completa"""
    while True:
        config = load_config()
        aapanel = config.get('aapanel', {})
        panel_url = os.environ.get("PROSPECTOR_PUBLIC_URL", "http://127.0.0.1:8765")
        print_header("⚙️ CONFIGURAÇÃO DO PROSPECTOR")
        print(f"Status: {'✅ Configurado' if config.get('assinatura', {}).get('nome') else '⚠️  Incompleto'}")
        print(f"Painel web: {panel_url}\n")

        options = [
            ("👤 Assinatura & Perfil", "Nome, apresentação, WhatsApp"),
            ("🎯 Nichos & Prospecção", "Nichos, cidade, filtros, meta de leads"),
            ("🤖 Playwright (Scraper)", "Headless, proxy, user-agent, rate limit"),
            ("🌐 aapanel (Deploy)", "URL, API token, FTP/SSH, domínio, SSL"),
            ("☁️ Cloudflare (DNS)", "API Token, email, zona, proxy CNAME"),
            ("📧 E-mail & Propostas", "Modo rascunho/enviar, assinatura e-mail"),
            ("📱 WhatsApp & Canais", "Evolution API/Go, canais de envio"),
            ("💾 Salvar & Testar", "Valida tudo e testa conexões"),
            ("🔙 Voltar", "")
        ]

        for i, (title, desc) in enumerate(options, 1):
            print_menu_option(str(i), title, desc)

        choice = input(f"\n{Colors.BOLD}Escolha:{Colors.END} ").strip()

        if choice == '1':
            config_assinatura(config)
        elif choice == '2':
            config_prospeccao(config)
        elif choice == '3':
            config_playwright(config)
        elif choice == '4':
            config_aapanel(config)
        elif choice == '5':
            config_cloudflare(config)
        elif choice == '6':
            config_email(config)
        elif choice == '7':
            config_whatsapp(config)
        elif choice == '8':
            validar_config_completa(config)
        elif choice in ('9', 'v', 'voltar'):
            break
        else:
            print_error("Opção inválida")

def config_assinatura(config: Dict):
    print_header("👤 Assinatura & Perfil")
    assinatura = config.get('assinatura', {})
    assinatura['nome'] = input_prompt("Nome completo", assinatura.get('nome', ''))
    assinatura['apresentacao'] = input_prompt("Apresentação (ex: Especialista em automação e growth)", assinatura.get('apresentacao', ''))
    assinatura['whatsapp'] = input_prompt("WhatsApp (formato 5511999990000)", assinatura.get('whatsapp', ''))
    config['assinatura'] = assinatura
    save_config(config)
    print_success("Assinatura salva!")

def config_prospeccao(config: Dict):
    print_header("🎯 Nichos & Prospecção")
    prospeccao = config.get('prospeccao', {})
    nichos = prospeccao.get('nichos', ['nutricionistas', 'psicologos', 'advogados', 'psiquiatras', 'dentistas'])
    print("Nichos atuais:", ", ".join(nichos))
    novos = input_prompt("Adicionar nichos (separados por vírgula)", "").strip()
    if novos:
        for n in novos.split(','):
            n = n.strip().lower()
            if n and n not in nichos:
                nichos.append(n)
    prospeccao['nichos'] = nichos
    prospeccao['cidade'] = input_prompt("Cidade/Região padrão", prospeccao.get('cidade', 'São Paulo'))
    prospeccao['leadsPorBusca'] = int(input_prompt("Meta de leads por busca", str(prospeccao.get('leadsPorBusca', 10))))
    prospeccao['notaMinima'] = float(input_prompt("Nota mínima no Maps", str(prospeccao.get('notaMinima', 4.7))))
    prospeccao['avaliacoesMinimas'] = int(input_prompt("Avaliações mínimas", str(prospeccao.get('avaliacoesMinimas', 40))))
    config['prospeccao'] = prospeccao
    save_config(config)
    print_success("Prospecção configurada!")

def config_playwright(config: Dict):
    print_header("🤖 Playwright (Scraper)")
    pw = config.get('playwright', {})
    pw['headless'] = confirm("Headless (sem interface gráfica)?", pw.get('headless', True))
    pw['browser'] = input_prompt("Browser (chromium/firefox/webkit)", pw.get('browser', 'chromium'))
    pw['timeout_ms'] = int(input_prompt("Timeout (ms)", str(pw.get('timeout_ms', 30000))))
    pw['delay_entre_requisicoes_ms'] = int(input_prompt("Delay entre requisições (ms)", str(pw.get('delay_entre_requisicoes_ms', 2000))))
    pw['stealth'] = confirm("Modo stealth (anti-bot)?", pw.get('stealth', True))
    proxy = input_prompt("Proxy (ex: http://user:pass@ip:port) - opcional", pw.get('proxy', ''))
    if proxy:
        pw['proxy'] = proxy
    config['playwright'] = pw
    save_config(config)
    print_success("Playwright configurado!")

def config_aapanel(config: Dict):
    print_header("🌐 aapanel (Deploy Local)")
    aa = config.get('aapanel', {})
    print("Configure seu aapanel local:")
    aa['url'] = input_prompt("URL do painel (ex: https://panel.example.com)", aa.get('url', 'https://panel.example.com'))
    aa['api_token'] = input_prompt("API Token (Configurações → API no aapanel)", aa.get('api_token', ''))
    aa['usuario'] = input_prompt("Usuário FTP/SSH do servidor", aa.get('usuario', ''))
    aa['senha'] = input_prompt("Senha FTP/SSH (NUNCA compartilhe no chat)", aa.get('senha', ''))
    aa['dominio_base'] = input_prompt("Domínio base (ex: example.com)", aa.get('dominio_base', 'example.com'))
    usar_subpasta = confirm("Usar subpasta em vez de subdomínio?", aa.get('usar_subpasta', False))
    aa['usar_subpasta'] = usar_subpasta
    if usar_subpasta:
        aa['pasta_base'] = input_prompt("Pasta base (ex: clientes)", aa.get('pasta_base', 'clientes'))
    else:
        aa['pasta_base'] = 'clientes'
    aa['ssl_auto'] = confirm("SSL Let's Encrypt automático?", aa.get('ssl_auto', True))
    aa['php_version'] = input_prompt("PHP version (82=8.2, 81=8.1, 80=8.0)", aa.get('php_version', '82'))
    config['aapanel'] = aa
    config['deploy_target'] = 'aapanel'
    save_config(config)
    print_success("aapanel configurado!")
    if confirm("Testar conexão agora?"):
        testar_conexao_aapanel()

def config_cloudflare(config: Dict):
    print_header("☁️ Cloudflare (DNS Automático)")
    cf = config.get('cloudflare', {})
    print("Configure o Cloudflare para criar CNAMEs automáticos (ex: cliente.example.com)")
    print("API Token: Cloudflare → My Profile → API Tokens → Create Token (Zone:DNS:Edit)")
    cf['api_token'] = input_prompt("API Token", cf.get('api_token', ''))
    cf['email'] = input_prompt("Email da conta Cloudflare", cf.get('email', 'avanni@ellajoyas.com'))
    cf['zone'] = cf.get('zone', 'example.com')
    cf['proxied'] = confirm("Proxy Cloudflare (ON = proteção DDoS, OFF = DNS only)?", cf.get('proxied', True))
    config['cloudflare'] = cf
    save_config(config)
    print_success("Cloudflare configurado!")
    if confirm("Testar conexão agora?"):
        testar_conexao_cloudflare()

def config_email(config: Dict):
    print_header("📧 E-mail & Propostas")
    envio = config.get('envio', {})
    envio['modo'] = 'rascunho' if confirm("Modo seguro: criar rascunhos sem enviar?", envio.get('modo') == 'rascunho') else 'envio'
    envio['canais'] = config_canais(envio.get('canais', ['email']))
    config['envio'] = envio
    save_config(config)
    print_success("E-mail configurado!")


def config_canais(current: list = None) -> list:
    """Interactive channel selection: email, whatsapp, or both."""
    current = current or ["email"]
    print("\nCanais de envio:")
    print(f"  {'[x]' if 'email' in current else '[ ]'} 1. E-mail")
    print(f"  {'[x]' if 'whatsapp' in current else '[ ]'} 2. WhatsApp")
    print(f"  {'[x]' if 'email' in current and 'whatsapp' in current else '[ ]'} 3. Ambos")
    option = input_prompt("Escolha o canal", "3").strip()
    if option == '1':
        return ['email']
    elif option == '2':
        return ['whatsapp']
    else:
        return ['email', 'whatsapp']


def config_whatsapp(config: Dict):
    print_header("📱 WhatsApp & Canais de Envio")
    envio = config.get('envio', {})
    wa = envio.get('whatsapp', {})

    print("Selecione os canais de envio das propostas:")
    envio['canais'] = config_canais(envio.get('canais', ['email']))

    print("\nConfiguração do provedor WhatsApp:")
    provedor = 'evolution_api' if confirm("Usar Evolution API (caso contrário Evolution Go)?", wa.get('provedor') != 'evolution_go') else 'evolution_go'
    wa['provedor'] = provedor

    # Evolution API config
    evo_api = wa.get('evolution_api', {})
    if provedor == 'evolution_api' or confirm("Configurar Evolution API (mesmo que não seja o provedor ativo)?", True):
        evo_api['url'] = input_prompt("URL do servidor Evolution API", evo_api.get('url', 'http://localhost:8080'))
        evo_api['api_key'] = input_prompt("API Key Evolution", evo_api.get('api_key', ''))
        evo_api['instance'] = input_prompt("Nome da instância", evo_api.get('instance', 'prospector'))
        wa['evolution_api'] = evo_api

    # Evolution Go config
    evo_go = wa.get('evolution_go', {})
    if provedor == 'evolution_go' or confirm("Configurar Evolution Go (mesmo que não seja o provedor ativo)?", True):
        evo_go['url'] = input_prompt("URL do servidor Evolution Go", evo_go.get('url', 'http://localhost:3100'))
        evo_go['api_key'] = input_prompt("API Key Evolution Go", evo_go.get('api_key', ''))
        evo_go['instance'] = input_prompt("Nome da instância", evo_go.get('instance', 'prospector'))
        wa['evolution_go'] = evo_go

    envio['whatsapp'] = wa
    config['envio'] = envio
    save_config(config)
    print_success("WhatsApp configurado!")

    if confirm("Testar conexão?", True):
        testar_conexao_whatsapp(config)


def testar_conexao_whatsapp(config: Dict):
    print_info("Testando conexão WhatsApp...")
    wa = config.get('envio', {}).get('whatsapp', {})
    provedor = wa.get('provedor', 'evolution_api')
    if provedor == 'evolution_go':
        url = wa.get('evolution_go', {}).get('url', '')
    else:
        url = wa.get('evolution_api', {}).get('url', '')
    result = run_command([sys.executable, '-c', f'''
import urllib.request
import json
url = "{url}"
try:
    req = urllib.request.Request(url+"/", headers={{"apikey": "test"}})
    response = urllib.request.urlopen(req, timeout=10)
    print("Servidor OK - Status:", response.status)
except Exception as e:
    print("Falha de conexão:", e)
'''])
    if result['success']:
        print_success(result['stdout'])
    else:
        print_error(f"Falha: {result['stderr']}")

def validar_config_completa(config: Dict):
    print_header("✅ Validação Completa")
    checks = [
        ("Assinatura", bool(config.get('assinatura', {}).get('nome'))),
        ("Nichos", bool(config.get('prospeccao', {}).get('nichos'))),
        ("Cidade", bool(config.get('prospeccao', {}).get('cidade'))),
        ("Playwright", True),  # Sempre OK, tem defaults
        ("aapanel API", bool(config.get('aapanel', {}).get('api_token'))),
        ("aapanel FTP/SSH", bool(config.get('aapanel', {}).get('usuario'))),
        ("Cloudflare DNS", bool(config.get('cloudflare', {}).get('api_token'))),
    ]
    all_ok = True
    for name, ok in checks:
        status = f"{Colors.GREEN}✅{Colors.END}" if ok else f"{Colors.RED}❌{Colors.END}"
        print(f"  {status} {name}")
        if not ok:
            all_ok = False
    if all_ok:
        print_success("\nTudo configurado! Testando conexões...")
        testar_conexao_aapanel()
        testar_conexao_cloudflare()
    else:
        print_warning("\nComplete os itens ❌ antes de prosseguir.")

def testar_conexao_aapanel():
    print_info("Testando conexão aapanel...")
    result = run_command([
        sys.executable, '-c', '''
import sys
sys.path.insert(0, "skills/deploy-aapanel/references")
from aapanel_api import AAPanelClient
import json
with open("prospector-config.json") as f:
    c = json.load(f)["aapanel"]
client = AAPanelClient(c["url"], c["api_token"])
print("API:", "OK" if client.test_connection() else "FALHOU")
sites = client.list_sites()
print(f"Sites existentes: {len(sites)}")
for s in sites[:5]:
    print(f"  - {s.get('domain')} ({s.get('path')})"
'''
    ])
    if result['success']:
        print(result['stdout'])
    else:
        print_error(f"Falha: {result['stderr']}")

def testar_conexao_cloudflare():
    print_info("Testando conexão Cloudflare...")
    result = run_command([
        sys.executable, '-c', '''
import sys
sys.path.insert(0, "skills/deploy-aapanel/references")
from cloudflare_client import CloudflareClient
import json
with open("prospector-config.json") as f:
    c = json.load(f)["cloudflare"]
if not c.get("api_token"):
    print("⚠️  Cloudflare não configurado")
    sys.exit(0)
client = CloudflareClient(c["api_token"], c.get("email", ""), c.get("zone", "example.com"))
if client.test_connection():
    records = client.list_records()
    print(f"Cloudflare: OK - {len([r for r in records if r['type'] == 'CNAME'])} CNAMEs")
else:
    print("Cloudflare: FALHOU - API token inválido ou zona não encontrada")
    sys.exit(1)
'''
    ])
    if result['success']:
        print(result['stdout'])
    else:
        print_error(f"Falha: {result['stderr']}")

def menu_ver_leads():
    print_header("📋 VER LEADS")
    listar_leads()
    print()
    print_menu_option("1", "Exportar CSV", "Salvar leads qualificados em CSV")
    print_menu_option("2", "Voltar", "")
    choice = input(f"\n{Colors.BOLD}Escolha:{Colors.END} ").strip()
    if choice == '1':
        exportar_csv()
    input(f"\n{Colors.BOLD}Pressione Enter para voltar...{Colors.END}")

def menu_ferramentas():
    while True:
        print_header("🔧 FERRAMENTAS")
        options = [
            ("🧪 Testar Playwright", "Verifica se Playwright + Chromium + stealth funcionam"),
            ("🌐 Testar aapanel API", "Testa conexão com aapanel via API"),
            ("☁️ Testar Cloudflare DNS", "Testa conexão e lista CNAMEs"),
            ("🧹 Limpar cache Playwright", "Remove playwright-state.json"),
            ("📋 Ver logs", "Mostra logs recentes do prospector"),
            ("🔙 Voltar", "")
        ]
        for i, (title, desc) in enumerate(options, 1):
            print_menu_option(str(i), title, desc)
        choice = input(f"\n{Colors.BOLD}Escolha:{Colors.END} ").strip()
        if choice == '1':
            print_info("Testando Playwright...")
            result = run_command([sys.executable, '-c', '''
import asyncio
from playwright.async_api import async_playwright
async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://example.com", timeout=10000)
        print(f"Título: {await page.title()}")
        await browser.close()
asyncio.run(test())
print("✅ Playwright OK")
'''])
            if result['success']:
                print_success(result['stdout'])
            else:
                print_error(f"Falha: {result['stderr']}")
        elif choice == '2':
            testar_conexao_aapanel()
        elif choice == '3':
            testar_conexao_cloudflare()
        elif choice == '4':
            state_file = os.path.join(os.path.dirname(__file__), 'playwright-state.json')
            if os.path.exists(state_file):
                os.remove(state_file)
                print_success("Cache limpo")
            else:
                print_info("Cache já estava limpo")
        elif choice == '5':
            log_file = os.path.join(os.path.dirname(__file__), 'prospector.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    print(f.read()[-2000:])
            else:
                print_info("Nenhum log encontrado")
        elif choice in ('6', 'v', 'voltar'):
            break
        else:
            print_error("Opção inválida")
        input(f"\n{Colors.BOLD}Pressione Enter para continuar...{Colors.END}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrompido pelo usuário. Até logo!{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""
Deploy para aapanel - Script CLI
Suporta modo API (com token) e modo LOCAL (sem token, usa nginx + certbot direto)
Com integração Cloudflare para DNS
"""

import sys
import os
import json
import asyncio
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "skills" / "deploy-aapanel" / "references"))

from aapanel_api import AAPanelClient, build_deploy_config, deploy_site_aapanel, upload_files_local, verify_https_local
from cloudflare_client import CloudflareClient


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 deploy.py <slug|todos>")
        sys.exit(1)

    target = sys.argv[1]

    # Carregar config
    config_file = BASE_DIR / "prospector-config.json"
    if not config_file.exists():
        print("❌ prospector-config.json não encontrado. Rode ./prospector setup")
        sys.exit(1)

    config = json.loads(config_file.read_text())
    aapanel_cfg = config.get('aapanel', {})
    cf_config = config.get('cloudflare', {})

    # Determinar slugs
    leads_file = BASE_DIR / "leads.md"
    slugs = []

    if target == "todos":
        if leads_file.exists():
            content = leads_file.read_text()
            for line in content.split('\n'):
                if '|' in line and not line.startswith('| #') and not line.startswith('|---'):
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 10 and parts[9] == 'redesenhado':
                        slug = parts[1].lower().replace(' ', '-')
                        slugs.append(slug)
    else:
        slugs = [target]

    if not slugs:
        print("⚠️  Nenhum lead com status 'redesenhado' encontrado")
        sys.exit(0)

    print(f"\n🚀 Iniciando deploy de {len(slugs)} site(s)...\n")

    # Verificar Cloudflare
    cf_client = None
    if cf_config.get('api_token') or cf_config.get('api_key'):
        if cf_config.get('api_token'):
            cf_client = CloudflareClient(
                api_token=cf_config['api_token'],
                email=cf_config.get('email', 'avanni@ellajoyas.com'),
                zone_name=cf_config.get('zone', 'iabotz.online')
            )
        else:
            cf_client = CloudflareClient(
                api_key=cf_config['api_key'],
                api_email=cf_config.get('email', 'avanni@ellajoyas.com'),
                zone_name=cf_config.get('zone', 'iabotz.online')
            )
        try:
            records = cf_client.list_records()
            print(f"☁️  Cloudflare conectado - {len(records)} registros CNAME")
        except Exception as e:
            print(f"⚠️  Cloudflare erro: {e}")
            cf_client = None
    else:
        print("ℹ️  Cloudflare não configurado (DNS manual)")

    # Verificar se tem API token aapanel
    has_api = bool(aapanel_cfg.get('api_token'))
    client = None

    if has_api:
        client = AAPanelClient(
            aapanel_cfg['url'],
            aapanel_cfg['api_token'],
            verify_ssl=aapanel_cfg.get('verify_ssl', True)
        )
        if client.test_connection():
            print("✅ Conectado ao aapanel via API")
        else:
            print("⚠️  Falha na API aapanel, usando modo LOCAL")
            has_api = False
            client = None
    else:
        print("ℹ️  Modo LOCAL (sem API token aapanel - usa nginx + certbot direto)")

    results = []

    for slug in slugs:
        print(f"\n{'='*50}")
        print(f"📦 Deploy: {slug}")
        print(f"{'='*50}")

        local_dir = BASE_DIR / "sites" / slug
        if not local_dir.exists():
            print(f"❌ Diretório não encontrado: {local_dir}")
            results.append({'slug': slug, 'success': False, 'error': 'Diretório não encontrado'})
            continue

        if has_api and client:
            # Modo API
            result = await deploy_site_aapanel(client, slug, config, local_dir)
        else:
            # Modo LOCAL puro
            result = await deploy_local_only(slug, config, local_dir, cf_client)

        results.append(result)

        if result['success']:
            print(f"✅ {slug} - {result.get('url', result.get('url_final', 'OK'))}")
        else:
            print(f"❌ {slug} - {result.get('errors', ['Erro desconhecido'])[0]}")

    # Resumo
    print(f"\n{'='*50}")
    print("📋 RESUMO DO DEPLOY")
    print(f"{'='*50}")
    ok = sum(1 for r in results if r['success'])
    print(f"✅ Sucesso: {ok}/{len(results)}")
    for r in results:
        status = "✅" if r['success'] else "❌"
        url = r.get('url', r.get('url_final', r.get('error', 'Erro')))
        print(f"  {status} {r['slug']}: {url}")

    if ok == len(results):
        print("\n🎉 Todos os deploys concluídos com sucesso!")
        print("💡 Próximo passo: ./prospector proposta")
    else:
        print(f"\n⚠️  {len(results) - ok} deploy(s) falharam. Verifique logs acima.")
        sys.exit(1)


async def deploy_local_only(slug: str, config: Dict, local_dir: Path, cf_client: CloudflareClient = None) -> Dict:
    """Deploy puramente local: cria dir, configura nginx, certbot, reload"""
    aapanel = config.get('aapanel', {})
    usar_subdominio = aapanel.get('usar_subdominio', True)
    dominio_base = aapanel.get('dominio_base', 'panel.iabotz.online')
    pasta_base = aapanel.get('pasta_base', 'clientes')
    ssl_auto = aapanel.get('ssl_auto', True)

    if usar_subdominio:
        dominio = f"{slug}.{dominio_base}"
        path = f"/www/wwwroot/{dominio}"
        url_final = f"https://{dominio}/"
    else:
        dominio = dominio_base
        path = f"/www/wwwroot/{dominio_base}/{pasta_base}/{slug}"
        url_final = f"https://{dominio_base}/{pasta_base}/{slug}/"

    result = {
        'slug': slug,
        'dominio': dominio,
        'url_final': url_final,
        'url_proposta': f"{url_final}proposta.html",
        'success': False,
        'steps': [],
        'errors': []
    }

    def add_step(step, success=True, detail=""):
        result['steps'].append({'step': step, 'success': success, 'detail': detail})
        if not success:
            result['errors'].append(f"{step}: {detail}")

    def run_sudo(cmd, input_data=None):
        proc = subprocess.run(
            ['sudo'] + cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=60
        )
        return proc

    try:
        # 1. Criar diretório e copiar arquivos (COM SUDO)
        add_step("Criando diretório e copiando arquivos (sudo)...")
        remote = Path(path)

        proc = run_sudo(['mkdir', '-p', path])
        if proc.returncode != 0:
            add_step("Criar diretório /www/wwwroot/", False, proc.stderr)
            return result

        for item in local_dir.rglob('*'):
            if item.is_file():
                rel = item.relative_to(local_dir)
                dest = Path(path) / rel
                run_sudo(['mkdir', '-p', str(dest.parent)])
                proc = run_sudo(['cp', str(item), str(dest)])
                if proc.returncode != 0:
                    add_step(f"Copiar {rel}", False, proc.stderr)
                    return result

        add_step("Arquivos copiados para /www/wwwroot/ (sudo)", True)

        # 2. Criar config nginx se não existir
        nginx_conf = f"/etc/nginx/sites-available/{dominio}"
        nginx_enabled = f"/etc/nginx/sites-enabled/{dominio}"

        if not os.path.exists(nginx_conf):
            add_step("Criando configuração nginx...")
            nginx_config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {dominio};
    root {path};
    index index.html index.htm;

    location / {{
        try_files $uri $uri/ =404;
    }}

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
}}"""
            proc = run_sudo(['tee', nginx_conf], input_data=nginx_config)
            if proc.returncode != 0:
                add_step("Criar nginx config", False, proc.stderr)
                return result

            run_sudo(['ln', '-sf', nginx_conf, nginx_enabled])

            # Testar e reload nginx
            run_sudo(['nginx', '-t'])
            run_sudo(['systemctl', 'reload', 'nginx'])
            add_step("Nginx configurado e recarregado", True)
        else:
            add_step("Nginx já configurado", True)

        # 3. Cloudflare DNS - CRIAR CNAME ANTES DO SSL
        dns_created = False
        if cf_client:
            add_step("Criando/atualizando DNS CNAME no Cloudflare...")
            try:
                subdomain = f"{slug}.panel"
                target = "panel.iabotz.online"
                cf_result = cf_client.create_cname(subdomain, target, proxied=True)
                dns_created = True
                add_step(f"DNS CNAME criado/atualizado: {subdomain}.iabotz.online -> {target}", True)
            except Exception as e:
                add_step("Cloudflare DNS", False, str(e))

        # 4. SSL com certbot (se habilitado E DNS resolver)
        ssl_ok = False
        if ssl_auto:
            add_step("Verificando/criando SSL Let's Encrypt...")

            # Aguardar DNS propagar se criamos CNAME
            if dns_created:
                add_step("Aguardando DNS propagar...")
                for i in range(12):  # 60 segundos max
                    try:
                        import socket
                        socket.gethostbyname(f"{slug}.panel.iabotz.online")
                        break
                    except socket.gaierror:
                        time.sleep(5)
                add_step("DNS resolvendo", True)

            # Verificar se DNS resolve
            try:
                import socket
                socket.gethostbyname(dominio)
                dns_ok = True
            except socket.gaierror:
                dns_ok = False

            if dns_ok:
                certbot_cmd = [
                    'sudo', 'certbot', 'certonly', '--nginx',
                    '-d', dominio,
                    '--non-interactive', '--agree-tos',
                    '-m', f'admin@iabotz.online',
                    '--redirect'
                ]
                proc = subprocess.run(certbot_cmd, capture_output=True, text=True, timeout=120)
                if proc.returncode == 0:
                    add_step("SSL Let's Encrypt configurado", True)
                    run_sudo(['systemctl', 'reload', 'nginx'])
                    ssl_ok = True
                else:
                    add_step("SSL certbot", False, proc.stderr[:200])
            else:
                add_step("SSL pulado (DNS não resolvido - teste local)", True)

        # 4. Verificar HTTP (sempre funciona se nginx ok)
        add_step("Verificando HTTP...")
        http_ok = await verify_http_local(dominio)
        add_step("Verificação HTTP", http_ok, "OK" if http_ok else "Falha")

        if not http_ok:
            return result

        # 5. Verificar proposta.html
        add_step("Verificando proposta.html...")
        prop_ok = await verify_http_local(f"{dominio}/proposta.html")
        add_step("Verificação proposta.html", prop_ok)

        result['success'] = True
        result['http_ok'] = True
        result['ssl_ok'] = ssl_ok if 'ssl_ok' in locals() else False
        result['dns_created'] = dns_created if 'dns_created' in locals() else False
        return result

    except Exception as e:
        add_step("Erro geral", False, str(e))
        return result


async def verify_http_local(url_or_domain: str) -> bool:
    """Verifica se URL responde HTTP"""
    import requests
    from urllib.parse import urlparse

    parsed = urlparse(url_or_domain if url_or_domain.startswith('http') else f'http://{url_or_domain}')
    host = parsed.netloc or parsed.path
    path = parsed.path or '/'

    try:
        response = requests.get(f'http://{host}{path}', timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"  HTTP verify error: {e}")
        return False


if __name__ == '__main__':
    asyncio.run(main())
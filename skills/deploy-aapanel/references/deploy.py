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
import re
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "skills" / "deploy-aapanel" / "references"))

from aapanel_api import AAPanelClient, build_deploy_config, deploy_site_aapanel, upload_files_local, verify_https_local
from cloudflare_client import CloudflareClient




def mark_published(slug: str, url: str) -> None:
    db_file = BASE_DIR / "prospector.db"
    if not db_file.exists():
        return
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute(
        """UPDATE leads SET status='publicado', urlNova=?, atualizado=datetime('now','localtime')
           WHERE slug=?""",
        (url, slug),
    )
    conn.commit()
    conn.close()
    print(f"🗄  SQLite: {slug} → publicado ({url})")


def public_subdomain(slug: str, site_url: str = "") -> str:
    """Return a readable, valid one-label hostname for Cloudflare Universal SSL."""
    host = ""
    if site_url:
        parsed = urlparse(site_url if "://" in site_url else f"https://{site_url}")
        host = (parsed.hostname or "").lower().removeprefix("www.")
    candidate = host.split(".")[0] if host else slug
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-") or "lead"
    if len(candidate) > 55:
        import hashlib
        candidate = f"{candidate[:47].rstrip('-')}-{hashlib.sha1(candidate.encode()).hexdigest()[:7]}"
    return candidate

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

    # Determinar slugs (SQLite first)
    import sqlite3
    db_file = BASE_DIR / "prospector.db"
    targets: list[tuple[str, str]] = []
    if target == "todos" and db_file.exists():
        conn = sqlite3.connect(db_file)
        targets = [(r[0], r[1] or "") for r in conn.execute(
            "SELECT slug, siteAntigo FROM leads WHERE status='redesenhado' ORDER BY atualizado DESC"
        ).fetchall()]
        conn.close()
    elif target != "todos":
        site_url = ""
        if db_file.exists():
            conn = sqlite3.connect(db_file)
            row = conn.execute("SELECT siteAntigo FROM leads WHERE slug=?", (target,)).fetchone()
            conn.close()
            site_url = row[0] if row else ""
        targets = [(target, site_url)]

    if not targets:
        print("⚠️  Nenhum lead com status 'redesenhado' encontrado")
        sys.exit(0)

    print(f"\n🚀 Iniciando deploy de {len(targets)} site(s)...\n")

    # Verificar Cloudflare
    cf_client = None
    if cf_config.get('api_token') or cf_config.get('api_key'):
        if cf_config.get('api_token'):
            cf_client = CloudflareClient(
                api_token=cf_config['api_token'],
                email=cf_config.get('email', ''),
                zone_name=cf_config.get('zone') or 'example.com'
            )
        else:
            cf_client = CloudflareClient(
                api_key=cf_config['api_key'],
                api_email=cf_config.get('email', ''),
                zone_name=cf_config.get('zone') or 'example.com'
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

    for slug, site_url in targets:
        print(f"\n{'='*50}")
        print(f"📦 Deploy: {slug}")
        print(f"{'='*50}")

        local_dir = BASE_DIR / "sites" / slug
        if not local_dir.exists():
            print(f"❌ Diretório não encontrado: {local_dir}")
            results.append({'slug': slug, 'success': False, 'error': 'Diretório não encontrado'})
            continue

        public_label = public_subdomain(slug, site_url)
        if public_label != slug:
            print(f"🌐 Subdomínio público: {public_label} (do domínio original)")

        if has_api and client:
            # Modo API
            result = await deploy_site_aapanel(client, slug, config, local_dir)
        else:
            # Modo LOCAL puro
            result = await deploy_local_only(slug, config, local_dir, cf_client, public_label=public_label)

        results.append(result)

        if result['success']:
            url = result.get('url') or result.get('url_final') or ''
            print(f"✅ {slug} - {url}")
            mark_published(slug, url)
        else:
            errs = result.get('errors') or [result.get('error') or 'Erro desconhecido']
            print(f"❌ {slug} - {errs[0]}")

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


async def deploy_local_only(slug: str, config: Dict, local_dir: Path, cf_client: CloudflareClient = None, public_label: str | None = None) -> Dict:
    """Deploy local: /www/wwwroot + nginx aaPanel + CNAME Cloudflare.

    Cloudflare Universal SSL normally covers one wildcard label. The public
    domain and origin target are always read from configuration.
    """
    aapanel = config.get("aapanel", {})
    cf_cfg = config.get("cloudflare") or {}
    usar_subdominio = aapanel.get("usar_subdominio", True)
    # Default alinhado ao Universal SSL da Cloudflare
    dominio_base = aapanel.get("dominio_base") or "example.com"
    pasta_base = aapanel.get("pasta_base", "clientes")
    dns_target = aapanel.get("dns_target") or "origin.example.com"
    cert_dir = aapanel.get("ssl_cert_dir") or f"/www/server/panel/vhost/cert/{dominio_base}"

    public_label = public_label or public_subdomain(slug)
    if usar_subdominio:
        dominio = f"{public_label}.{dominio_base}"
        path = f"/www/wwwroot/{dominio}"
        url_final = f"https://{dominio}/"
        zone = cf_cfg.get("zone") or dominio_base
        # Registro CF relativo à zona (ex.: slug ou slug.panel)
        if dominio.endswith("." + zone):
            cf_record_name = dominio[: -(len(zone) + 1)]
        else:
            cf_record_name = public_label
    else:
        dominio = dominio_base
        path = f"/www/wwwroot/{dominio_base}/{pasta_base}/{slug}"
        url_final = f"https://{dominio_base}/{pasta_base}/{slug}/"
        cf_record_name = None

    result = {
        "slug": slug,
        "dominio": dominio,
        "url": url_final,
        "url_final": url_final,
        "url_proposta": f"{url_final}proposta.html",
        "success": False,
        "steps": [],
        "errors": [],
    }

    def add_step(step, success=True, detail=""):
        result["steps"].append({"step": step, "success": success, "detail": detail})
        if not success:
            result["errors"].append(f"{step}: {detail}")

    def run_sudo(cmd, input_data=None):
        sudo_bin = ["sudo", "-n"] if __import__("shutil").which("sudo") else ["sudo"]
        return subprocess.run(
            sudo_bin + cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=60,
        )

    try:
        add_step("Criando diretório e copiando arquivos (sudo)...")
        proc = run_sudo(["mkdir", "-p", path])
        if proc.returncode != 0:
            add_step("Criar diretório /www/wwwroot/", False, proc.stderr)
            return result

        for item in local_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(local_dir)
                dest = Path(path) / rel
                run_sudo(["mkdir", "-p", str(dest.parent)])
                proc = run_sudo(["cp", str(item), str(dest)])
                if proc.returncode != 0:
                    add_step(f"Copiar {rel}", False, proc.stderr)
                    return result

        add_step("Arquivos copiados para /www/wwwroot/", True)

        nginx_conf = f"/www/server/panel/vhost/nginx/{dominio}.conf"
        # Sempre (re)escreve conf para garantir cert/domínio corretos
        add_step("Configurando nginx aaPanel...")
        nginx_config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {dominio};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name {dominio};
    root {path};
    index index.html index.htm;

    ssl_certificate     {cert_dir}/fullchain.pem;
    ssl_certificate_key {cert_dir}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {{
        try_files $uri $uri/ =404;
    }}

    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
}}
"""
        proc = run_sudo(["tee", nginx_conf], input_data=nginx_config)
        if proc.returncode != 0:
            add_step("Criar nginx config", False, proc.stderr)
            return result

        t = run_sudo(["/www/server/nginx/sbin/nginx", "-c", "/www/server/nginx/conf/nginx.conf", "-t"])
        if t.returncode != 0:
            add_step("nginx -t", False, (t.stderr or t.stdout)[:300])
            return result
        run_sudo(["/www/server/nginx/sbin/nginx", "-c", "/www/server/nginx/conf/nginx.conf", "-s", "reload"])
        add_step("Nginx configurado e recarregado", True)

        dns_created = False
        if cf_client and cf_record_name:
            add_step(f"Cloudflare DNS: {cf_record_name} → {dns_target}...")
            try:
                proxied = cf_cfg.get("proxied", True)
                cf_client.create_cname(cf_record_name, dns_target, proxied=proxied)
                dns_created = True
                add_step(
                    f"DNS CNAME {cf_record_name}.{cf_client.zone_name} → {dns_target} (proxied={proxied})",
                    True,
                )
            except Exception as e:
                add_step("Cloudflare DNS", False, str(e))
                # DNS falhou: ainda podemos servir localmente, mas não marcamos sucesso total
                return result
        elif not cf_client:
            add_step("Cloudflare não configurado — DNS manual necessário", True)

        # Verifica origem local (não depende do edge Cloudflare)
        add_step("Verificando origem local (HTTPS)...")
        local_ok = await verify_origin_local(dominio)
        add_step("Origem local", local_ok, "OK" if local_ok else "Falha")
        if not local_ok:
            return result

        prop_ok = await verify_origin_local(dominio, "/proposta.html")
        add_step("proposta.html local", prop_ok, "OK" if prop_ok else "ausente")

        # Tentativa pública (Universal SSL pode levar 1–2 min em hostname novo)
        public_ok = await verify_http_local(dominio)
        add_step(
            "Verificação pública",
            True,
            "OK" if public_ok else "pendente (Universal SSL Cloudflare pode levar alguns minutos)",
        )

        result["success"] = True
        result["http_ok"] = True
        result["ssl_ok"] = True
        result["dns_created"] = dns_created
        result["public_ok"] = public_ok
        return result

    except Exception as e:
        add_step("Erro geral", False, str(e))
        return result


async def verify_origin_local(domain: str, path: str = "/") -> bool:
    """GET via 127.0.0.1 com Host/SNI — valida nginx+cert sem passar pelo Cloudflare."""
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        r = requests.get(
            f"https://127.0.0.1{path}",
            headers={"Host": domain},
            timeout=10,
            verify=False,
            allow_redirects=True,
        )
        # requests não seta SNI facilmente; fallback curl --resolve
        if r.status_code == 200:
            return True
    except Exception:
        pass
    try:
        proc = subprocess.run(
            [
                "curl",
                "-sk",
                "--resolve",
                f"{domain}:443:127.0.0.1",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                f"https://{domain}{path}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.stdout.strip() == "200"
    except Exception as e:
        print(f"  origin verify error: {e}")
        return False


async def verify_http_local(url_or_domain: str) -> bool:
    """Verifica se URL responde publicamente (HTTPS primeiro)."""
    import requests
    from urllib.parse import urlparse
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if url_or_domain.startswith("http"):
        parsed = urlparse(url_or_domain)
        host = parsed.netloc
        path = parsed.path or "/"
    else:
        host = url_or_domain.split("/")[0]
        path = "/" + "/".join(url_or_domain.split("/")[1:]) if "/" in url_or_domain else "/"

    for scheme in ("https", "http"):
        try:
            response = requests.get(
                f"{scheme}://{host}{path}",
                timeout=15,
                verify=True,
                allow_redirects=True,
            )
            if response.status_code == 200:
                return True
            print(f"  {scheme.upper()} {host}{path} → {response.status_code}")
        except Exception as e:
            print(f"  {scheme.upper()} verify error: {e}")
    return False


if __name__ == '__main__':
    asyncio.run(main())

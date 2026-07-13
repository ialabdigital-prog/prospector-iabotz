#!/usr/bin/env python3
"""
Cliente Python para API do aapanel
Gerencia sites, SSL, FTP via API REST
Agora suporta deploy LOCAL (escrita direta em /www/wwwroot/) já que rodamos no mesmo servidor
"""

import os
import shutil
import time
import json
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path
from urllib.parse import urljoin


class AAPanelClient:
    """Cliente para API do aapanel"""

    def __init__(self, base_url: str, api_token: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        })
        self.session.verify = verify_ssl

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Faz requisição para API do aapanel"""
        url = urljoin(f"{self.base_url}/api", endpoint)
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro API aapanel {method} {endpoint}: {e}")

    def _post(self, endpoint: str, data: Dict) -> Dict:
        return self._request('POST', endpoint, json=data)

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        return self._request('GET', endpoint, params=params)

    # ========== SITES ==========

    def list_sites(self) -> List[Dict]:
        """Lista todos os sites"""
        result = self._post('/site/list', {})
        return result.get('data', []) if isinstance(result, dict) else result

    def get_site(self, domain: str) -> Optional[Dict]:
        """Busca site por domínio"""
        sites = self.list_sites()
        for site in sites:
            if site.get('domain') == domain:
                return site
        return None

    def create_site(self, domain: str, path: str, php_version: str = '82',
                    ssl: bool = True, site_type: str = 'php') -> Dict:
        """
        Cria novo site
        php_version: '80'=8.0, '81'=8.1, '82'=8.2, '83'=8.3
        site_type: 'php', 'nodejs', 'python', 'go', 'static'
        """
        data = {
            'domain': domain,
            'path': path,
            'php_version': php_version,
            'ssl': 1 if ssl else 0,
            'type': site_type
        }
        return self._post('/site/create', data)

    def delete_site(self, site_id: int) -> Dict:
        """Deleta site pelo ID"""
        return self._post('/site/delete', {'id': site_id})

    def set_site_ssl(self, domain: str, ssl_type: int = 1) -> Dict:
        """Configura SSL do site (1=Let's Encrypt, 2=Custom)"""
        return self._post('/site/set_ssl', {'domain': domain, 'ssl_type': ssl_type})

    # ========== SSL ==========

    def create_lets_ssl(self, domain: str, email: str = 'admin@localhost') -> Dict:
        """Cria certificado Let's Encrypt"""
        return self._post('/ssl/create_lets_ssl', {
            'domain': domain,
            'email': email,
            'dns': 'auto'
        })

    def renew_lets_ssl(self, domain: str) -> Dict:
        """Renova certificado Let's Encrypt"""
        return self._post('/ssl/renew_lets_ssl', {'domain': domain})

    def get_ssl_info(self, domain: str) -> Dict:
        """Obtém info do certificado SSL"""
        return self._post('/ssl/get_ssl_info', {'domain': domain})

    def wait_ssl_ready(self, domain: str, timeout: int = 120, interval: int = 5) -> bool:
        """Aguarda SSL ficar pronto (polling)"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                info = self.get_ssl_info(domain)
                if info.get('status') == 1:
                    return True
                if info.get('status') == -1:
                    raise Exception(f"SSL falhou: {info.get('msg', 'Erro desconhecido')}")
            except Exception as e:
                print(f"  ⏳ Aguardando SSL para {domain}... ({e})")
            time.sleep(interval)
        return False

    # ========== FTP ==========

    def create_ftp(self, username: str, password: str, path: str,
                   domain: str = None, permission: str = 'rw') -> Dict:
        """Cria usuário FTP"""
        data = {
            'username': username,
            'password': password,
            'path': path,
            'permission': permission
        }
        if domain:
            data['domain'] = domain
        return self._post('/ftp/create', data)

    def list_ftp(self) -> List[Dict]:
        """Lista usuários FTP"""
        result = self._post('/ftp/list', {})
        return result.get('data', []) if isinstance(result, dict) else result

    def delete_ftp(self, ftp_id: int) -> Dict:
        """Deleta usuário FTP"""
        return self._post('/ftp/delete', {'id': ftp_id})

    # ========== DATABASE ==========

    def create_database(self, name: str, username: str, password: str,
                        domain: str = None) -> Dict:
        """Cria banco de dados MySQL"""
        data = {
            'name': name,
            'username': username,
            'password': password,
            'charset': 'utf8mb4'
        }
        if domain:
            data['domain'] = domain
        return self._post('/database/create', data)

    # ========== UTILITÁRIOS ==========

    def get_system_info(self) -> Dict:
        """Info do sistema"""
        return self._post('/system/get_info', {})

    def test_connection(self) -> bool:
        """Testa conexão com API"""
        try:
            result = self.get_system_info()
            return 'data' in result or 'version' in str(result)
        except:
            return False


# ============================================================
# HELPERS PARA DEPLOY DO PROSPECTOR
# ============================================================

def build_deploy_config(config: Dict, slug: str) -> Dict:
    """Gera configuração de deploy para um slug"""
    aapanel = config.get('aapanel', {})
    usar_subdominio = aapanel.get('usar_subdominio', True)
    dominio_base = aapanel.get('dominio_base', 'example.com')
    pasta_base = aapanel.get('pasta_base', 'clientes')
    php_version = aapanel.get('php_version', '82')
    ssl_auto = aapanel.get('ssl_auto', True)

    if usar_subdominio:
        dominio = f"{slug}.{dominio_base}"
        path = f"/www/wwwroot/{dominio}"
        url_final = f"https://{dominio}/"
    else:
        dominio = dominio_base
        path = f"/www/wwwroot/{dominio_base}/{pasta_base}/{slug}"
        url_final = f"https://{dominio_base}/{pasta_base}/{slug}/"

    return {
        'dominio': dominio,
        'path': path,
        'url_final': url_final,
        'url_proposta': f"{url_final}proposta.html",
        'php_version': php_version,
        'ssl_auto': ssl_auto,
        'usar_subdominio': usar_subdominio,
        'dominio_base': dominio_base,
        'pasta_base': pasta_base
    }


async def deploy_site_aapanel(client: 'AAPanelClient', slug: str,
                               config: Dict, local_dir: Path) -> Dict:
    """
    Deploy completo de um site no aapanel (MODO LOCAL - escrita direta em /www/wwwroot/)
    """
    deploy_cfg = build_deploy_config(config, slug)
    dominio = deploy_cfg['dominio']
    path = deploy_cfg['path']
    url_final = deploy_cfg['url_final']
    ssl_auto = deploy_cfg['ssl_auto']

    result = {
        'slug': slug,
        'dominio': dominio,
        'url': url_final,
        'url_proposta': deploy_cfg['url_proposta'],
        'success': False,
        'steps': [],
        'errors': []
    }

    def add_step(step: str, success: bool = True, detail: str = ""):
        result['steps'].append({'step': step, 'success': success, 'detail': detail})
        if not success:
            result['errors'].append(f"{step}: {detail}")

    try:
        # 1. Verificar/criar site
        add_step("Verificando site existente")
        existing = client.get_site(dominio)

        if existing:
            add_step(f"Site já existe (ID: {existing.get('id')})", True)
            site_id = existing.get('id')
        else:
            add_step("Criando site no aapanel...")
            create_result = client.create_site(
                domain=dominio,
                path=path,
                php_version=deploy_cfg['php_version'],
                ssl=deploy_cfg['ssl_auto']
            )
            if create_result.get('status') == 1 or create_result.get('success'):
                site_id = create_result.get('data', {}).get('id') or create_result.get('id')
                add_step(f"Site criado (ID: {site_id})", True)
            else:
                add_step("Criar site", False, str(create_result))
                return result

        # 2. SSL Let's Encrypt
        if ssl_auto:
            add_step("Verificando/criando SSL Let's Encrypt...")
            ssl_info = client.get_ssl_info(dominio)

            if ssl_info.get('status') != 1:
                ssl_result = client.create_lets_ssl(dominio)
                add_step("Solicitando certificado SSL",
                         ssl_result.get('status') == 1 or ssl_result.get('success'),
                         str(ssl_result))

                # Aguardar SSL
                if client.wait_ssl_ready(dominio, timeout=180):
                    add_step("SSL emitido e ativo", True)
                else:
                    add_step("SSL timeout - certificado não emitido a tempo", False)
                    return result
            else:
                add_step("SSL já ativo", True)

        # 3. Upload dos arquivos (LOCAL - cópia direta)
        add_step("Enviando arquivos para /www/wwwroot/...")
        upload_ok = await upload_files_local(path, local_dir)
        add_step("Upload arquivos", upload_ok,
                 "Arquivos copiados" if upload_ok else "Falha na cópia")

        if not upload_ok:
            return result

        # 4. Verificação HTTPS (BLOQUEANTE)
        add_step("Verificando HTTPS...")
        https_ok = await verify_https_local(dominio)
        add_step("Verificação HTTPS", https_ok,
                 "OK - Certificado válido" if https_ok else "Falha - HTTPS não acessível")

        if not https_ok:
            return result

        # 5. Verificar proposta.html
        add_step("Verificando proposta.html...")
        prop_ok = await verify_https_local(f"{dominio}/proposta.html")
        add_step("Verificação proposta.html", prop_ok)

        result['success'] = True
        return result

    except Exception as e:
        add_step("Erro geral", False, str(e))
        return result


async def upload_files_local(remote_path: str, local_dir: Path) -> bool:
    """Copia arquivos locais para /www/wwwroot/ (mesmo servidor)"""
    try:
        remote = Path(remote_path)
        remote.mkdir(parents=True, exist_ok=True)

        # Copia recursiva preservando estrutura
        for item in local_dir.rglob('*'):
            if item.is_file():
                rel = item.relative_to(local_dir)
                dest = remote / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)

        return True
    except Exception as e:
        print(f"  Erro upload local: {e}")
        return False


async def verify_https_local(url_or_domain: str) -> bool:
    """Verifica se URL responde HTTPS com certificado válido"""
    import ssl
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(url_or_domain if url_or_domain.startswith('http') else f'https://{url_or_domain}')
    host = parsed.netloc or parsed.path
    path = parsed.path or '/'

    try:
        # Teste HTTP
        response = requests.get(f'https://{host}{path}', timeout=10, verify=True)
        if response.status_code != 200:
            return False

        # Teste certificado
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                # Verificar expiração
                import datetime
                exp_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                if exp_date < datetime.datetime.now():
                    return False

        return True
    except Exception as e:
        print(f"  HTTPS verify error: {e}")
        return False


import requests
if __name__ == '__main__':
    # Teste rápido
    import asyncio
    config = {
        'aapanel': {
            'url': 'https://panel.example.com',
            'api_token': 'SEU_TOKEN_AQUI',
            'usuario': 'root',
            'senha': 'senha_ssh',
            'dominio_base': 'example.com',
            'pasta_base': 'clientes',
            'usar_subdominio': True,
            'ssl_auto': True,
            'php_version': '82'
        }
    }

    client = AAPanelClient(config['aapanel']['url'], config['aapanel']['api_token'])
    print("Testando conexão...")
    print(f"Conectado: {client.test_connection()}")

    sites = client.list_sites()
    print(f"Sites: {len(sites)}")
    for s in sites[:5]:
        print(f"  - {s.get('domain')} ({s.get('path')})")

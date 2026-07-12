#!/usr/bin/env python3
"""
Cliente API aapanel para deploy automático
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import paramiko
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class DeployResult:
    slug: str
    success: bool
    url_principal: str = ""
    url_proposta: str = ""
    error: str = ""


class AAPanelClient:
    def __init__(self, config: Dict):
        self.config = config.get('aapanel', {})
        self.base_url = self.config.get('url', '').rstrip('/')
        self.api_token = self.config.get('api_token', '')
        self.usuario = self.config.get('usuario', '')
        self.senha = self.config.get('senha', '')
        self.dominio_base = self.config.get('dominio_base', '')
        self.pasta_base = self.config.get('pasta_base', 'clientes')
        self.usar_subdominio = self.config.get('usar_subdominio', True)
        self.php_version = self.config.get('php_version', '82')
        self.ssl_auto = self.config.get('ssl_auto', True)
        
        # Sessão HTTP com retry
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update({'Authorization': f'Bearer {self.api_token}'})
        self.session.verify = False  # aapanel costuma usar cert auto-assinado

    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Faz request para API do aapanel"""
        url = f"{self.base_url}/api{endpoint}"
        try:
            if method == 'GET':
                resp = self.session.get(url, params=data, timeout=30)
            else:
                resp = self.session.post(url, json=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {'error': str(e), 'status': getattr(e.response, 'status_code', 0) if e.response else 0}

    def create_site(self, slug: str) -> Dict:
        """Cria site no aapanel"""
        if self.usar_subdominio:
            domain = f"{slug}.{self.dominio_base}"
            path = f"/www/wwwroot/{domain}"
        else:
            domain = self.dominio_base
            path = f"/www/wwwroot/{self.dominio_base}/{self.pasta_base}/{slug}"
        
        data = {
            'domain': domain,
            'path': path,
            'php_version': self.php_version,
            'ssl': 1 if self.ssl_auto else 0
        }
        return self._request('POST', '/site/create', data)

    def set_ssl(self, domain: str) -> Dict:
        """Configura SSL Let's Encrypt"""
        data = {'domain': domain, 'type': 'letsencrypt'}
        return self._request('POST', '/site/set_ssl', data)

    def get_ssl_status(self, domain: str) -> Dict:
        """Verifica status do SSL"""
        return self._request('GET', '/site/get_ssl', {'domain': domain})

    def wait_ssl(self, domain: str, max_wait: int = 120) -> bool:
        """Aguarda SSL ficar pronto"""
        start = time.time()
        while time.time() - start < max_wait:
            status = self.get_ssl_status(domain)
            if status.get('status') == 1:  # Sucesso
                return True
            if status.get('status') == -1:  # Erro
                return False
            time.sleep(5)
        return False

    def list_sites(self) -> Dict:
        return self._request('GET', '/site/list')

    def delete_site(self, domain: str) -> Dict:
        return self._request('POST', '/site/delete', {'domain': domain})


class SFTPUploader:
    """Upload via SFTP/rsync"""
    
    def __init__(self, host: str, usuario: str, senha: str, porta: int = 22):
        self.host = host
        self.usuario = usuario
        self.senha = senha
        self.porta = porta
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp = None

    def connect(self) -> bool:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.host, 
                port=self.porta, 
                username=self.usuario, 
                password=self.senha,
                timeout=30
            )
            self.sftp = self.client.open_sftp()
            return True
        except Exception as e:
            print(f"Erro SFTP connect: {e}")
            return False

    def upload_dir(self, local_dir: Path, remote_dir: str) -> bool:
        """Upload recursivo de diretório"""
        try:
            # Criar diretório remoto se não existe
            self._mkdir_p(remote_dir)
            
            for root, dirs, files in os.walk(local_dir):
                rel_path = Path(root).relative_to(local_dir)
                remote_path = f"{remote_dir}/{rel_path}" if str(rel_path) != '.' else remote_dir
                
                # Criar subdiretórios
                self._mkdir_p(remote_path)
                
                # Upload arquivos
                for file in files:
                    local_file = Path(root) / file
                    remote_file = f"{remote_path}/{file}"
                    self.sftp.put(str(local_file), remote_file)
            
            return True
        except Exception as e:
            print(f"Erro upload: {e}")
            return False

    def _mkdir_p(self, remote_path: str):
        """Cria diretório recursivo"""
        parts = remote_path.strip('/').split('/')
        current = ''
        for part in parts:
            current += f'/{part}'
            try:
                self.sftp.stat(current)
            except IOError:
                self.sftp.mkdir(current)

    def close(self):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()


async def deploy_via_rsync(local_dir: Path, remote_host: str, remote_user: str, remote_path: str) -> bool:
    """Deploy via rsync (mais rápido que SFTP)"""
    try:
        # Extrair host do URL se necessário
        if remote_host.startswith('http'):
            from urllib.parse import urlparse
            parsed = urlparse(remote_host)
            remote_host = parsed.hostname or remote_host
        
        cmd = [
            'rsync', '-avz', '--delete',
            '-e', f'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null',
            f'{local_dir}/',
            f'{remote_user}@{remote_host}:{remote_path}/'
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            return True
        print(f"rsync erro: {stderr.decode()}")
        return False
    except Exception as e:
        print(f"Erro rsync: {e}")
        return False


async def deploy_cliente(
    slug: str,
    sites_dir: Path,
    aapanel: AAPanelClient,
    uploader: SFTPUploader
) -> DeployResult:
    """Deploy completo de um cliente"""
    domain = f"{slug}.{aapanel.dominio_base}" if aapanel.usar_subdominio else aapanel.dominio_base
    remote_path = f"/www/wwwroot/{domain}" if aapanel.usar_subdominio else f"/www/wwwroot/{aapanel.dominio_base}/{aapanel.pasta_base}/{slug}"
    local_site = sites_dir / slug
    
    if not local_site.exists():
        return DeployResult(slug, False, error=f"Pasta local não encontrada: {local_site}")
    
    print(f"🚀 Deployando {slug} → {domain}")
    
    # 1. Criar site no aapanel
    print("  📝 Criando site no aapanel...")
    create_resp = aapanel.create_site(slug)
    if 'error' in create_resp:
        return DeployResult(slug, False, error=f"Criar site: {create_resp['error']}")
    
    # 2. SSL
    if aapanel.ssl_auto:
        print("  🔒 Configurando SSL...")
        ssl_resp = aapanel.set_ssl(domain)
        if 'error' not in ssl_resp:
            print("  ⏳ Aguardando SSL...")
            if not aapanel.wait_ssl(domain):
                return DeployResult(slug, False, error="SSL timeout/erro")
    
    # 3. Upload arquivos
    print("  📤 Upload dos arquivos...")
    if aapanel.usuario and aapanel.senha:
        # SFTP
        if not uploader.connect():
            return DeployResult(slug, False, error="Falha conexão SFTP")
        success = uploader.upload_dir(local_site, remote_path)
        uploader.close()
    else:
        # rsync
        host = aapanel.base_url.replace('https://', '').replace('http://', '').split(':')[0]
        success = await deploy_via_rsync(local_site, host, aapanel.usuario or 'root', remote_path)
    
    if not success:
        return DeployResult(slug, False, error="Falha no upload")
    
    # 4. Verificar HTTPS
    print("  ✅ Verificando HTTPS...")
    url_principal = f"https://{domain}/"
    url_proposta = f"https://{domain}/proposta.html"
    
    for attempt in range(3):
        try:
            resp = requests.get(url_principal, timeout=15, verify=True)
            if resp.status_code == 200:
                break
        except:
            pass
        await asyncio.sleep(5)
    else:
        return DeployResult(slug, False, error="HTTPS não responde após deploy")
    
    print(f"  ✨ Deploy OK: {url_principal}")
    return DeployResult(slug, True, url_principal, url_proposta)


async def main():
    """Entry point para deploy em lote"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deploy aapanel - Publicador automático')
    parser.add_argument('slugs', nargs='*', help='Slugs dos clientes para deploy (ou "todos")')
    parser.add_argument('--config', default='prospector-config.json', help='Config file')
    parser.add_argument('--sites-dir', default='sites', help='Diretório dos sites locais')
    parser.add_argument('--fila', default='fila-publicacao.txt', help='Arquivo de fila (compat HostGator)')
    args = parser.parse_args()
    
    # Carregar config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ Config não encontrado: {config_path}")
        sys.exit(1)
    
    config = json.loads(config_path.read_text())
    aapanel_config = config.get('aapanel', {})
    
    if not aapanel_config.get('api_token'):
        print("❌ API token do aapanel não configurado")
        sys.exit(1)
    
    # Inicializar clientes
    aapanel = AAPanelClient(config)
    uploader = SFTPUploader(
        host=aapanel.base_url.replace('https://', '').replace('http://', '').split(':')[0],
        usuario=aapanel.usuario,
        senha=aapanel.senha
    ) if aapanel.usuario and aapanel.senha else None
    
    sites_dir = Path(args.sites_dir)
    if not sites_dir.exists():
        sites_dir = Path(__file__).parent.parent.parent.parent / args.sites_dir
    
    # Determinar alvos
    if not args.slugs or 'todos' in args.slugs:
        slugs = [d.name for d in sites_dir.iterdir() if d.is_dir()]
    else:
        slugs = args.slugs
    
    if not slugs:
        print("Nenhum cliente para deploy")
        return
    
    print(f"📦 Deploy de {len(slugs)} cliente(s)")
    
    results = []
    for slug in slugs:
        result = await deploy_cliente(slug, sites_dir, aapanel, uploader)
        results.append(result)
        
        # Atualizar leads.md se existir
        leads_file = Path(__file__).parent.parent.parent.parent / 'leads.md'
        if leads_file.exists():
            update_leads_md(leads_file, slug, result)
    
    # Resumo
    ok = sum(1 for r in results if r.success)
    print(f"\n✅ {ok}/{len(results)} deployados com sucesso")
    for r in results:
        if r.success:
            print(f"   ✅ {r.slug}: {r.url_principal}")
        else:
            print(f"   ❌ {r.slug}: {r.error}")


def update_leads_md(leads_file: Path, slug: str, result: DeployResult):
    """Atualiza leads.md com URL do deploy"""
    lines = leads_file.read_text().split('\n')
    for i, line in enumerate(lines):
        if f'| {slug} |' in line or f'|{slug}|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 10:
                parts[8] = 'publicado'  # Status
                parts[9] = result.url_principal  # URL nova
                lines[i] = '| ' + ' | '.join(parts[1:-1]) + ' |'
    leads_file.write_text('\n'.join(lines))


if __name__ == '__main__':
    asyncio.run(main())
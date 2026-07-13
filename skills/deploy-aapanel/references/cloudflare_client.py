#!/usr/bin/env python3
"""
Cliente Cloudflare para gerenciamento de DNS
Suporta tanto API Tokens (scoped) quanto Global API Keys (api_key + api_email)
Cria/atualiza CNAME records para subdomínios de prospects
"""

import os
import json
import time
import re
from typing import Dict, List, Optional, Any
from cloudflare import Cloudflare


class CloudflareClient:
    """Cliente para gerenciar DNS no Cloudflare"""

    def __init__(
        self,
        api_token: str = None,
        api_key: str = None,
        api_email: str = None,
        zone_name: str = "example.com"
    ):
        """
        Inicializa cliente Cloudflare.
        
        Suporta dois métodos de autenticação:
        1. API Token (scoped): api_token="xxx"
        2. Global API Key: api_key="xxx" + api_email="xxx@domain.com"
        
        Args:
            api_token: API Token scoped (formato novo)
            api_key: Global API Key (32+ chars, formato antigo)
            api_email: Email da conta Cloudflare (obrigatório com api_key)
            zone_name: Nome da zona DNS (ex: example.com)
        """
        self.zone_name = zone_name
        self._zone_id = None
        
        if api_token:
            # Método novo: API Token scoped
            self.client = Cloudflare(api_token=api_token)
        elif api_key and api_email:
            # Método antigo: Global API Key + Email
            self.client = Cloudflare(api_key=api_key, api_email=api_email)
        else:
            raise ValueError("Forneça api_token OU (api_key + api_email)")

    def _get_zone_id(self) -> str:
        """Obtém o Zone ID do domínio"""
        if self._zone_id:
            return self._zone_id

        zones = self.client.zones.list(name=self.zone_name)
        for zone in zones:
            if zone.name == self.zone_name:
                self._zone_id = zone.id
                return zone.id
        raise Exception(f"Zona {self.zone_name} não encontrada")

    # ========== DNS RECORDS ==========

    def list_records(self, record_type: str = "CNAME") -> List[Dict]:
        """Lista todos os registros DNS"""
        zone_id = self._get_zone_id()
        records = self.client.dns.records.list(zone_id=zone_id, type=record_type)
        return [
            {
                'id': r.id,
                'name': r.name,
                'type': r.type,
                'content': r.content,
                'proxied': r.proxied,
                'ttl': r.ttl
            }
            for r in records
        ]

    def get_record(self, name: str, record_type: str = "CNAME") -> Optional[Dict]:
        """Busca registro por nome (aceita relativo ou FQDN)."""
        zone_id = self._get_zone_id()
        # Normaliza para FQDN
        fqdn = name if name.endswith(self.zone_name) else f"{name}.{self.zone_name}"
        records = self.client.dns.records.list(zone_id=zone_id, type=record_type, name=fqdn)
        for r in records:
            if r.name in (name, fqdn, f"{name}.{self.zone_name}"):
                return {
                    "id": r.id,
                    "name": r.name,
                    "type": r.type,
                    "content": r.content,
                    "proxied": r.proxied,
                    "ttl": r.ttl,
                }
        # Fallback: listar e filtrar (algumas contas ignoram name=)
        for r in self.client.dns.records.list(zone_id=zone_id, type=record_type):
            if r.name in (fqdn, name):
                return {
                    "id": r.id,
                    "name": r.name,
                    "type": r.type,
                    "content": r.content,
                    "proxied": r.proxied,
                    "ttl": r.ttl,
                }
        return None

    def create_cname(self, subdomain: str, target: str, proxied: bool = True, ttl: int = 1) -> Dict:
        """Cria ou atualiza CNAME. subdomain = relativo à zona (ex.: 'cliente' ou 'cliente.panel')."""
        labels = subdomain.strip(".").split(".")
        if not labels or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
            raise ValueError(f"Subdomínio DNS inválido: {subdomain}")
        zone_id = self._get_zone_id()
        name = subdomain
        existing = self.get_record(subdomain)
        if existing:
            return self.update_cname(existing["id"], existing["name"], target, proxied)

        try:
            record = self.client.dns.records.create(
                zone_id=zone_id,
                type="CNAME",
                name=name,
                content=target,
                proxied=proxied,
                ttl=ttl,
            )
            return {"success": True, "id": record.id, "record": record}
        except Exception as exc:
            # A parallel deploy can create the same record after our initial
            # lookup. Cloudflare then returns 81053; retry the lookup and use
            # the record that won the race instead of failing the deploy.
            if "81053" not in str(exc):
                raise
            time.sleep(1)
            existing = self.get_record(subdomain)
            if existing:
                return self.update_cname(existing["id"], existing["name"], target, proxied)
            raise

    def update_cname(self, record_id: str, name: str, target: str, proxied: bool = True) -> Dict:
        """Atualiza registro CNAME existente"""
        zone_id = self._get_zone_id()
        
        record = self.client.dns.records.update(
            zone_id=zone_id,
            dns_record_id=record_id,
            type="CNAME",
            name=name,
            content=target,
            proxied=proxied,
            ttl=1
        )
        return {"success": True, "id": record.id, "record": record}

    def delete_record(self, name: str, record_type: str = "CNAME") -> bool:
        """Deleta registro DNS"""
        zone_id = self._get_zone_id()
        records = self.client.dns.records.list(zone_id=zone_id, type=record_type, name=name)
        for r in records:
            if r.name == name:
                self.client.dns.records.delete(zone_id=zone_id, dns_record_id=r.id)
                return True
        return False

    def verify_dns_resolves(self, subdomain: str) -> bool:
        """Verifica se o DNS resolve (para SSL)"""
        import socket
        try:
            full_domain = f"{subdomain}.{self.zone_name}"
            socket.gethostbyname(full_domain)
            return True
        except socket.gaierror:
            return False


# ============================================================
# HELPER PARA DEPLOY
# ============================================================

def get_cloudflare_client(config: Dict) -> Optional[CloudflareClient]:
    """Cria cliente Cloudflare a partir do config"""
    cf_config = config.get('cloudflare', {})
    api_token = cf_config.get('api_token')
    api_key = cf_config.get('api_key')
    api_email = cf_config.get('email')
    zone = cf_config.get('zone') or 'example.com'

    # Se tem api_key + email, usa Global API Key
    # Se tem api_token, usa API Token
    if api_key and api_email:
        return CloudflareClient(api_key=api_key, api_email=api_email, zone_name=zone)
    elif api_token:
        return CloudflareClient(api_token=api_token, zone_name=zone)
    return None


def create_prospect_dns(slug: str, config: Dict) -> Dict:
    """Cria DNS CNAME para prospect via Cloudflare"""
    cf = get_cloudflare_client(config)
    if not cf:
        return {'success': False, 'error': 'Cloudflare não configurado'}

    subdomain = f"{slug}.panel"
    target = (config.get("aapanel") or {}).get("dns_target") or "origin.example.com"

    return cf.create_cname(subdomain, target, proxied=True)


def verify_dns_ready(slug: str, config: Dict, max_wait: int = 60) -> bool:
    """Aguarda DNS propagar"""
    cf = get_cloudflare_client(config)
    if not cf:
        return False

    subdomain = f"{slug}.panel"
    import time
    start = time.time()
    while time.time() - start < max_wait:
        if cf.verify_dns_resolves(f"{slug}.panel"):
            return True
        time.sleep(5)
    return False

#!/usr/bin/env python3
"""
Follow-up - Envia follow-up para leads que não responderam à proposta
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))


def load_leads() -> List[Dict]:
    """Carrega leads do leads.md"""
    leads_file = BASE_DIR / "leads.md"
    if not leads_file.exists():
        return []
    
    leads = []
    content = leads_file.read_text(encoding='utf-8')
    for line in content.split('\n'):
        if '|' in line and not line.startswith('| #') and not line.startswith('|---'):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 11:
                leads.append({
                    'slug': parts[1].lower().replace(' ', '-'),
                    'nome': parts[1],
                    'nota': parts[2],
                    'avaliacoes': parts[3],
                    'email': parts[4],
                    'telefone': parts[5],
                    'whatsapp': parts[6],
                    'site_atual': parts[7],
                    'motivo': parts[8],
                    'status': parts[9],
                    'url_nova': parts[10] if len(parts) > 10 else '',
                    'data_proposta': parts[11] if len(parts) > 11 else ''
                })
    return leads


def load_config() -> Dict:
    """Carrega configuração"""
    config_file = BASE_DIR / "prospector-config.json"
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text())


def generate_followup_subject(lead: Dict) -> str:
    """Gera assunto do follow-up"""
    nome = lead['nome'].split()[0] if lead['nome'] else 'Olá'
    assuntos = [
        f"Re: {nome}, conseguiu ver a página?",
        f"Conseguiu dar uma olhada, {nome}?",
        f"{nome}, só passando pra saber se viu",
    ]
    idx = hash(lead['slug']) % len(assuntos)
    return assuntos[idx][:60]


def generate_followup_body(lead: Dict, config: Dict) -> str:
    """Gera corpo do follow-up"""
    assinatura = config.get('assinatura', {})
    nome = assinatura.get('nome', '')
    apresentacao = assinatura.get('apresentacao', '')
    whatsapp = assinatura.get('whatsapp', '')
    
    url_capa = f"{(lead.get('urlNova') or '').rstrip('/')}/proposta.html"
    
    return f"""<!DOCTYPE html>
<html>
<body style="font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
    <p>Oi {lead['nome'].split()[0]},</p>
    
    <p>Só passando pra saber se conseguiu dar uma olhada na nova versão do site que te mandei.</p>
    
    <p style="text-align: center; margin: 24px 0;">
        <a href="{url_capa}" style="display: inline-block; background: #1e40af; color: #fff; padding: 12px 24px; border-radius: 8px; font-weight: 600; text-decoration: none;">
            Ver a proposta →
        </a>
    </p>
    
    <p>Qualquer dúvida tô à disposição. Se não for o momento, sem problemas — só me avisa.</p>
    
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
    
    <p style="margin: 0;"><strong>{assinatura.get('nome', '')}</strong><br>
    {assinatura.get('apresentacao', '')}<br>
    📱 <a href="https://wa.me/{assinatura.get('whatsapp', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}" style="color: #1e40af;">{whatsapp}</a></p>
</body>
</html>"""


def is_followup_due(lead: Dict) -> bool:
    """Verifica se follow-up é devido (≥3 dias úteis após proposta)"""
    if lead['status'] not in ['proposta', 'proposta enviada']:
        return False
    if not lead['data_proposta']:
        return False
    
    try:
        data_prop = datetime.fromisoformat(lead['data_proposta'])
    except:
        return False
    
    hoje = datetime.now()
    dias_uteis = 0
    atual = data_prop
    while atual < hoje:
        atual += timedelta(days=1)
        if atual.weekday() < 5:  # Seg-Sex
            dias_uteis += 1
    
    return dias_uteis >= 3


async def create_followup_draft(lead: Dict, config: Dict) -> Dict:
    """Cria rascunho de follow-up"""
    assinatura = config.get('assinatura', {})
    
    subject = f"Re: {generate_followup_subject(lead)}"
    body = generate_followup_body(lead, config)
    
    # Salva localmente
    draft_dir = BASE_DIR / "drafts"
    draft_dir.mkdir(exist_ok=True)
    draft_file = BASE_DIR / "drafts" / f"followup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead['slug']}.html"
    
    draft_content = f"""Subject: {subject}
To: {lead['email']}
From: {assinatura.get('email', 'seu@email.com')}

{generate_followup_body(lead, config)}
"""
    
    draft_file.write_text(generate_followup_body(lead, config), encoding='utf-8')
    
    return {
        'success': True,
        'lead': lead['nome'],
        'subject': subject,
        'draft_file': str(draft_file),
        'message': 'Follow-up salvo localmente. Revise e envie via Gmail.'
    }


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 followup.py [slug|todos]")
        sys.exit(1)
    
    target = sys.argv[1]
    
    config = load_config()
    leads = load_leads()
    
    if not leads:
        print("⚠️  Nenhum lead encontrado")
        return
    
    # Filtra leads que precisam de follow-up
    if target == "todos":
        targets = [l for l in leads if is_followup_due(l)]
    else:
        targets = [l for l in leads if l['slug'] == target and is_followup_due(l)]
    
    if not targets:
        print("✅ Nenhum follow-up devido no momento")
        return
    
    print(f"\n📧 Gerando follow-ups para {len(targets)} lead(s)...\n")
    
    for lead in targets:
        result = await create_followup_draft(lead, config)
        if result['success']:
            print(f"✅ {lead['nome']}: follow-up criado")
            print(f"   Assunto: {result['subject']}")
        else:
            print(f"❌ {lead['nome']}: erro")
    
    print(f"\n📧 {len(targets)} follow-up(s) gerado(s)")
    print("💡 Revise em ./drafts/ e envie via Gmail")


if __name__ == '__main__':
    asyncio.run(main())

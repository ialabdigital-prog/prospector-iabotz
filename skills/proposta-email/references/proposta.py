#!/usr/bin/env python3
"""
Proposta Email - Gera rascunho de proposta no Gmail via Composio MCP
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Carrega template da capa
TEMPLATE_FILE = Path(__file__).parent / "capa-proposta-template.html"

@dataclass
class Lead:
    slug: str
    nome: str
    nicho: str
    cidade: str
    email: str
    telefone: str
    whatsapp: str
    site_atual: str
    motivo: str
    url_nova: str = ""

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
            if len(parts) >= 12:
                leads.append({
                    'slug': parts[2].lower().replace(' ', '-'),
                    'nome': parts[2],
                    'nota': parts[3],
                    'avaliacoes': parts[4],
                    'email': parts[5],
                    'telefone': parts[6],
                    'whatsapp': parts[7],
                    'site_atual': parts[8],
                    'motivo': parts[9],
                    'status': parts[10],
                    'url_nova': parts[11] if len(parts) > 11 else ''
                })
    return leads


def load_template() -> str:
    """Carrega template da capa"""
    if TEMPLATE_FILE.exists():
        return TEMPLATE_FILE.read_text(encoding='utf-8')
    return ""


def render_capa_template(template: str, lead: Dict, config: Dict) -> str:
    """Renderiza template da capa de proposta"""
    assinatura = config.get('assinatura', {})
    
    return template.replace(
        '{{NOME_CLIENTE}}', lead['nome']
    ).replace(
        '{{SCREENSHOT_ANTIGO_OU_PLACEHOLDER}}', f'<img src="https://webcache.googleusercontent.com/search?q=cache:{lead["site_atual"]}" alt="Site antigo" style="max-width:100%;border-radius:8px;">'
    ).replace(
        '{{SCREENSHOT_NOVO_OU_PLACEHOLDER}}', f'<img src="{lead["url_nova"]}" alt="Site novo" style="max-width:100%;border-radius:8px;">'
    ).replace(
        '{{MOTIVOS_SITE_RUIM}}', lead['motivo']
    ).replace(
        '{{URL_NOVA}}', lead['url_nova']
    ).replace(
        '{{URL_PROPOSTA}}', f"{lead['url_nova']}proposta.html"
    ).replace(
        '{{ASSINATURA_NOME}}', assinatura.get('nome', '')
    ).replace(
        '{{ASSINATURA_APRESENTACAO}}', assinatura.get('apresentacao', '')
    ).replace(
        '{{ASSINATURA_WHATSAPP}}', assinatura.get('whatsapp', '')
    ).replace(
        '{{ASSINATURA_WHATSAPP_FORMATADO}}', assinatura.get('whatsapp', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    )


def generate_subject(lead: Dict) -> str:
    """Gera assunto do e-mail (≤60 chars, pergunta pessoal)"""
    nome = lead['nome'].split()[0] if lead['nome'] else 'Olá'
    assuntos = [
        f"{nome}, posso te mostrar uma coisa sobre seu site?",
        f"Preparei algo para a {lead['nome']}",
        f"Vi seu site e pensei na {lead['nome']}",
        f"{nome}, seu site está perdendo clientes?",
        f"Uma nova versão para {lead['nome']}?",
    ]
    # Escolhe baseado no hash do slug para consistência
    idx = hash(lead['slug']) % len(assuntos)
    assunto = assuntos[idx]
    return assunto[:60]


def generate_email_body(lead: Dict, config: Dict) -> str:
    """Gera corpo do e-mail em HTML"""
    assinatura = config.get('assinatura', {})
    nome = assinatura.get('nome', '')
    apresentacao = assinatura.get('apresentacao', '')
    whatsapp = assinatura.get('whatsapp', '')
    
    # Extrai detalhes do motivo para o parágrafo 2
    motivos = lead['motivo'].split('; ') if '; ' in lead['motivo'] else [lead['motivo']]
    motivo1 = motivos[0] if motivos else 'o site não reflete a qualidade do seu trabalho'
    motivo2 = motivos[1] if len(motivos) > 1 else 'faltam informações claras para o paciente agendar'
    
    url_capa = f"{lead['url_nova']}proposta.html"
    
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
    <p>Dra./Dr. {lead['nome'].split()[0]},</p>
    
    <p>Encontrei a <strong>{lead['nome']}</strong> no Google Maps e fiquei impressionado com as <strong>{lead['avaliacoes']} avaliações</strong> e nota <strong>{lead['nota']}</strong> — sinal claro de que seus pacientes confiam no seu trabalho.</p>
    
    <p>Dando uma olhada no site atual, notei dois pontos que podem estar fazendo você perder agendamentos: <strong>{motivo1.lower()}</strong> e <strong>{motivo2.lower()}</strong>. Nada que uma versão moderna não resolva.</p>
    
    <p>Por isso, <strong>preparei uma nova versão completa do site, já no ar</strong> — com design responsivo, SEO local, botão de WhatsApp fixo, depoimentos integrados e formulário de agendamento.</p>
    
    <p style="text-align: center; margin: 32px 0;">
        <a href="{url_capa}" style="display: inline-block; background: #1e40af; color: #fff; padding: 14px 28px; border-radius: 8px; font-weight: 600; text-decoration: none; font-size: 16px;">
            Ver o antes/depois →
        </a>
    </p>
    
    <p>Abra no celular também — o layout se adapta perfeitamente. O link é a proposta: se gostar, a gente conversa sobre valores e prazos. Sem pressão.</p>
    
    <p>Conseguiu dar uma olhada? Me diz o que achou.</p>
    
    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
    
    <p style="margin: 0;"><strong>{nome}</strong><br>
    {apresentacao}<br>
    📱 <a href="https://wa.me/{assinatura.get('whatsapp', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}" style="color: #1e40af;">{whatsapp}</a></p>
</body>
</html>"""
    
    return html


def validate_email(subject: str, body: str) -> List[str]:
    """Valida checklist anti-spam"""
    errors = []
    
    # 1 link só (a capa)
    links = body.count('href=')
    if links > 2:  # 1 link + maybe unsubscribe
        errors.append(f"Muitos links ({links}) - máximo 1 link principal")
    
    # Sem encurtador
    if 'bit.ly' in body or 'tinyurl' in body or 'short' in body:
        errors.append("Encurtador de URL detectado")
    
    # Link como âncora HTML
    if 'href="' in body and '>https://' not in body:
        pass  # OK se for âncora
    
    # Domínio limpo (não verificar aqui, já validado no config)
    
    # Palavras-gatilho
    gatilhos = ['grátis', 'promoção', 'imperdível', 'oferta', 'desconto', 'clique aqui', '100%', 'garantido', 'urgente']
    for g in gatilhos:
        if g in body.lower():
            errors.append(f"Palavra-gatilho: '{g}'")
    
    # CAIXA ALTA no assunto
    if subject.isupper():
        errors.append("Assunto em CAIXA ALTA")
    if '!!' in subject:
        errors.append("Assunto com '!!'")
    if any(c in subject for c in '😀😃😄😁😆😅😂🤣😊😇'):
        errors.append("Emoji no assunto")
    
    # HTML minimalista
    if 'style=' in body and ('color:' in body or 'font-' in body):
        pass  # OK se minimalista
    
    # Assunto ≤ 60 chars
    if len(subject) > 60:
        errors.append(f"Assunto muito longo ({len(subject)} chars, máx 60)")
    
    # Primeira linha personalizada
    primeiro_nome = lead['nome'].split()[0] if lead['nome'] else ''
    if primeiro_nome and primeiro_nome.lower() not in body.lower():
        errors.append("Primeira linha não personalizada com nome do lead")
    
    return errors


async def create_gmail_draft(lead: Dict, config: Dict) -> Dict:
    """Cria rascunho no Gmail via Composio MCP"""
    # Este é um placeholder - a implementação real usa o MCP do Composio
    # que já está configurado com a conta Gmail
    
    subject = generate_subject(lead)
    body = generate_email_body(lead, config)
    errors = validate_email(subject, body)
    
    if errors:
        return {'success': False, 'errors': errors, 'subject': subject, 'body': body}
    
    # Aqui entraria a chamada real ao MCP do Composio:
    # from composio import Composio
    # composio = Composio(api_key=os.getenv('COMPOSIO_API_KEY'))
    # draft = composio.gmail.create_draft(
    #     to=lead['email'],
    #     subject=subject,
    #     body=body,
    #     html=True
    # )
    
    # Por enquanto, salva localmente para revisão
    draft_dir = BASE_DIR / "drafts"
    draft_dir.mkdir(exist_ok=True)
    draft_file = draft_dir / f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{lead['slug']}.html"
    
    draft_content = f"""Subject: {subject}
To: {lead['email']}
From: {config.get('assinatura', {}).get('email', 'seu@email.com')}

{'' if isinstance(body, str) else body}
"""
    
    # O body já é HTML, salva como .html para abrir no browser
    draft_file.write_text(body, encoding='utf-8')
    
    return {
        'success': True,
        'lead': lead['nome'],
        'subject': subject,
        'draft_file': str(draft_file),
        'message': 'Rascunho salvo localmente. Abra no browser, revise e envie via Gmail.'
    }


async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 proposta.py <slug|todos>")
        sys.exit(1)
    
    target = sys.argv[1]
    
    # Carrega config
    config_file = BASE_DIR / "prospector-config.json"
    if not config_file.exists():
        print("❌ prospector-config.json não encontrado. Rode ./prospector setup")
        return
    
    config = json.loads(config_file.read_text())
    
    # Carrega template
    template = load_template()
    if not template:
        print("❌ Template da capa não encontrado")
        return
    
    # Carrega leads
    leads = load_leads()
    if not leads:
        print("⚠️  Nenhum lead encontrado no leads.md")
        return
    
    # Filtra leads
    if target == "todos":
        targets = [l for l in leads if l['status'] == 'publicado' and l['url_nova']]
    else:
        targets = [l for l in leads if l['slug'] == target]
    
    if not targets:
        print("⚠️  Nenhum lead publicado com URL encontrado")
        return
    
    print(f"\n📧 Gerando propostas para {len(targets)} lead(s)...\n")
    
    for lead in targets:
        # Renderiza capa
        lead['url_nova'] = lead['url_nova'] or f"https://{lead['slug']}.panel.iabotz.online/"
        capa_html = render_capa_template(template, lead, config)
        
        # Salva capa
        capa_dir = BASE_DIR / "sites" / lead['slug']
        capa_dir.mkdir(parents=True, exist_ok=True)
        (capa_dir / "proposta.html").write_text(capa_html, encoding='utf-8')
        
        # Gera e-mail
        lead['url_nova'] = f"https://{lead['slug']}.panel.iabotz.online/"
        result = await create_gmail_draft(lead, config)
        
        if result['success']:
            print(f"✅ {lead['nome']}: rascunho criado")
            print(f"   Assunto: {result['subject']}")
            print(f"   Arquivo: {result['draft_file']}")
        else:
            print(f"❌ {lead['nome']}: erros de validação")
            for err in result['errors']:
                print(f"   - {err}")
    
    print(f"\n📧 {len(targets)} proposta(s) processada(s)")
    print("💡 Revise os rascunhos em ./drafts/ e envie via Gmail")
    print("💡 Próximo: ./prospector followup (após 3+ dias sem resposta)")


if __name__ == '__main__':
    asyncio.run(main())
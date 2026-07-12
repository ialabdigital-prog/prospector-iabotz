#!/usr/bin/env python3
"""
Redesign Premium - Gera site premium, editor visual e comparador antes/depois
"""
import sys
import os
import json
import asyncio
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load config directly from JSON
config_file = BASE_DIR / "skills" / "redesign-premium" / "references" / "redesign-config.json"
config = json.loads(config_file.read_text(encoding='utf-8'))
SECTIONS = config["sections"]
CSS_VARIABLES = config["css_variables"]
BREAKPOINTS = config["breakpoints"]
EDITOR_SNIPPETS = config["editor_snippets"]


@dataclass
class Lead:
    slug: str
    nome: str
    nicho: str
    cidade: str
    nota: str = ""
    avaliacoes: str = ""
    email: str = ""
    telefone: str = ""
    whatsapp: str = ""
    site_atual: str = ""
    motivo: str = ""
    status: str = ""
    url_nova: str = ""
    endereco: str = ""


def load_lead(slug: str) -> Optional[Lead]:
    """Carrega lead do SQLite (fonte da verdade) com fallback leads.md."""
    db_file = BASE_DIR / "prospector.db"
    if db_file.exists():
        import sqlite3
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM leads WHERE slug=?", (slug,)).fetchone()
        conn.close()
        if row:
            return Lead(
                slug=row["slug"],
                nome=row["nome"] or slug,
                nicho=row["nicho"] or "",
                cidade=row["cidade"] or "",
                nota=str(row["nota"] or ""),
                avaliacoes=str(row["avaliacoes"] or ""),
                email=row["email"] or "",
                telefone=row["telefone"] or "",
                whatsapp=row["whatsapp"] or "",
                site_atual=row["siteAntigo"] or "",
                motivo=row["motivo"] or "",
                status=row["status"] or "",
                url_nova=row["urlNova"] or "",
            )

    leads_file = BASE_DIR / "leads.md"
    if not leads_file.exists():
        return None

    content = leads_file.read_text(encoding="utf-8")
    for line in content.split("\n"):
        if "|" not in line or line.startswith("| #") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        # # | Nome | Nota | Aval | Email | Tel | WA | Site | Motivo | Status | URL
        if len(parts) < 10:
            continue
        nome = parts[1] if parts[0].replace(".", "").isdigit() else parts[0]
        lead_slug = "".join(
            c for c in __import__("unicodedata").normalize("NFKD", nome.lower())
            if not __import__("unicodedata").combining(c)
        )
        import re
        lead_slug = re.sub(r"[^a-z0-9]+", "-", lead_slug).strip("-")
        if lead_slug == slug or nome.lower().replace(" ", "-") == slug:
            idx = 1 if parts[0].replace(".", "").isdigit() else 0
            return Lead(
                slug=slug,
                nome=parts[idx],
                nota=parts[idx + 1] if len(parts) > idx + 1 else "",
                avaliacoes=parts[idx + 2] if len(parts) > idx + 2 else "",
                email=parts[idx + 3] if len(parts) > idx + 3 else "",
                telefone=parts[idx + 4] if len(parts) > idx + 4 else "",
                whatsapp=parts[idx + 5] if len(parts) > idx + 5 else "",
                site_atual=parts[idx + 6] if len(parts) > idx + 6 else "",
                motivo=parts[idx + 7] if len(parts) > idx + 7 else "",
                status=parts[idx + 8] if len(parts) > idx + 8 else "",
                url_nova=parts[idx + 9] if len(parts) > idx + 9 else "",
                cidade="",
                nicho="",
            )
    return None


def mark_redesigned(slug: str) -> None:
    db_file = BASE_DIR / "prospector.db"
    if not db_file.exists():
        return
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute(
        """UPDATE leads SET status='redesenhado', atualizado=datetime('now','localtime')
           WHERE slug=? AND status IN ('novo','descartado','redesenhado')""",
        (slug,),
    )
    conn.commit()
    conn.close()


def list_slugs_for_redesign(target: str) -> List[str]:
    db_file = BASE_DIR / "prospector.db"
    if db_file.exists():
        import sqlite3
        conn = sqlite3.connect(db_file)
        if target == "todos":
            rows = conn.execute(
                "SELECT slug FROM leads WHERE status='novo' ORDER BY atualizado DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT slug FROM leads WHERE slug=?", (target,)
            ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    return [target] if target != "todos" else []


def extract_content_from_site(url: str) -> Dict:
    """Extrai conteúdo do site atual (placeholder - usar Playwright em produção)"""
    # Em produção, usar Playwright para extrair conteúdo real
    return {
        'titulo': '',
        'sobre': '',
        'servicos': [],
        'depoimentos': [],
        'equipe': [],
        'contato': {},
        'cores': {'primary': '#1e40af', 'secondary': '#0f172a'},
        'logo_url': '',
        'imagens': []
    }


def generate_css_variables(cores: Dict) -> str:
    """Gera CSS custom properties"""
    return f"""
:root {{
    --color-primary: {cores.get('primary', '#1e40af')};
    --color-secondary: {cores.get('secondary', '#0f172a')};
    --color-accent: {cores.get('accent', '#059669')};
    --color-bg: {cores.get('bg', '#f8fafc')};
    --color-card: #ffffff;
    --color-border: #e2e8f0;
    --color-text: #0f172a;
    --color-muted: #64748b;
    --font-heading: 'Inter', system-ui, sans-serif;
    --font-body: 'Inter', system-ui, sans-serif;
    --spacing-unit: 1rem;
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --shadow-sm: 0 1px 2px rgba(0,0,0,.05);
    --shadow-md: 0 4px 12px rgba(0,0,0,.08);
    --shadow-lg: 0 12px 32px rgba(0,0,0,.12);
}}"""


def generate_hero(lead: Lead, conteudo: Dict) -> str:
    headline = conteudo.get('hero_headline') or f"{lead.nicho.title()} em {lead.cidade} - {lead.nome}"
    subheadline = conteudo.get('hero_subheadline') or "Atendimento humanizado, resultados reais. Agende sua consulta."
    whatsapp_link = f"https://wa.me/{lead.whatsapp}" if lead.whatsapp else "#"
    
    return f'''
<section class="hero" style="--hero-bg: url('{conteudo.get("hero_image", "")}') center/cover no-repeat;">
    <div class="container">
        <h1>{headline}</h1>
        <p>{subheadline}</p>
        <div class="cta-group">
            <a href="{whatsapp_link}" class="btn btn-primary" target="_blank">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.476-1.91-1.786-.32-.254-.45-.45-.523-.578-.075-.128.222-.297.534-.644.64-.642 1.753-2.063 2.01-2.69.258-.627.258-1.294.01-1.676-.276-.43-1.003-2.35-1.492-3.14C9.07 3.38 8.573 3.23 8.073 3.1c-.475-.128-1.328-.07-2.012.247-.748.354-1.534 1.144-1.965 1.686-.372.47-.59.985-.622 1.216-.032.222-.097.45-.128.552-.06.22-.133.63-.133.715 0 .108.372.85.49 1.088.12.25.49 1.46.77 1.53.28.07 1.54.2 2.01.24.48.04 1.22.11 1.58.34.35.22.62.51.84.74.96.13.13.77.34 1.78.99 1.23.77 2.04 1.86 2.28 2.19.24.34.38.87.42 1.11.04.24.04.49-.09.66-.13.17-.44.47-1.2.53-1.5.14-2.7.17-4.2.17-1.37 0-2.56-.33-3.25-1.17"></path></svg>
                WhatsApp
            </a>
            <a href="#contato" class="btn btn-secondary">Agendar Consulta</a>
        </div>
    </div>
</section>'''


def generate_sobre(lead: Lead, conteudo: Dict) -> str:
    sobre = conteudo.get('sobre') or f"A {lead.nome} é referência em {lead.nicho} na região de {lead.cidade}. Com anos de experiência e compromisso com a excelência, oferecemos atendimento personalizado e tratamentos de ponta."
    credenciais = conteudo.get('credenciais', [])
    
    cred_html = ""
    if credenciais:
        cred_html = "<ul class='credenciais'>" + "".join(f"<li>{c}</li>" for c in credenciais) + "</ul>"
    
    return f'''
<section class="sobre" id="sobre">
    <div class="container">
        <h2>Sobre a {lead.nome}</h2>
        <div class="sobre-grid">
            <div class="sobre-texto">
                <p>{sobre}</p>
                {cred_html}
            </div>
            <div class="sobre-imagem">
                <img src="{conteudo.get('sobre_imagem', '')}" alt="{lead.nome}" loading="lazy">
            </div>
        </div>
    </div>
</section>'''


def generate_servicos(lead: Lead, conteudo: Dict) -> str:
    servicos = conteudo.get('servicos', [])
    if not servicos:
        # Serviços padrão baseados no nicho
        servicos_padrao = {
            'nutricionistas': [
                {'titulo': 'Consulta Nutricional', 'descricao': 'Avaliação completa e plano alimentar personalizado', 'icone': '🥗'},
                {'titulo': 'Reeducação Alimentar', 'descricao': 'Mudança de hábitos sustentável sem dietas restritivas', 'icone': '🌱'},
                {'titulo': 'Nutrição Esportiva', 'descricao': 'Performance e recuperação para atletas', 'icone': '🏃'},
            ],
            'psicologos': [
                {'titulo': 'Terapia Individual', 'descricao': 'Atendimento humanizado para ansiedade, depressão e autoconhecimento', 'icone': '💬'},
                {'titulo': 'Terapia de Casal', 'descricao': 'Fortalecimento do relacionamento e comunicação', 'icone': '💑'},
                {'titulo': 'Orientação Vocacional', 'descricao': 'Descoberta de propósito e direcionamento de carreira', 'icone': '🎯'},
            ],
        }
        servicos = servicos_padrao.get(lead.nicho.lower(), [
            {'titulo': 'Serviço 1', 'descricao': 'Descrição do serviço', 'icone': '✨'},
            {'titulo': 'Serviço 2', 'descricao': 'Descrição do serviço', 'icone': '✨'},
        ])
    
    cards = ""
    for s in servicos:
        cards += f"""
        <article class="servico-card">
            <div class="servico-icon">{s.get('icone', '✨')}</div>
            <h3>{s['titulo']}</h3>
            <p>{s['descricao']}</p>
            <a href="#contato" class="servico-cta">Saiba mais →</a>
        </article>"""
    
    return f'''
<section class="servicos" id="servicos">
    <div class="container">
        <h2>Nossos Serviços</h2>
        <div class="servicos-grid">
            {cards}
        </div>
    </div>
</section>'''


def generate_depoimentos(lead: Lead, conteudo: Dict) -> str:
    depoimentos = conteudo.get('depoimentos', [])
    if not depoimentos:
        return ""
    
    cards = ""
    for d in depoimentos:
        stars = "⭐" * int(d.get('avaliacao', 5))
        cards += f"""
        <article class="depoimento-card">
            <div class="depoimento-stars">{stars}</div>
            <p class="depoimento-texto">"{d.get('texto', '')}"</p>
            <div class="depoimento-autor">
                <img src="{d.get('foto', '')}" alt="{d.get('nome', '')}" loading="lazy">
                <div>
                    <strong>{d.get('nome', '')}</strong>
                    <span>{d.get('cargo', '')}</span>
                </div>
            </div>
        </article>"""
    
    return f'''
<section class="depoimentos" id="depoimentos">
    <div class="container">
        <h2>O que dizem nossos pacientes</h2>
        <div class="depoimentos-carousel">
            {cards}
        </div>
        <a href="{lead.site_atual}" target="_blank" class="btn btn-outline">Ver todos no Google Maps →</a>
    </div>
</section>'''


def generate_faq(lead: Lead, conteudo: Dict) -> str:
    faqs = conteudo.get('faq', [])
    if not faqs:
        faqs_padrao = {
            'nutricionistas': [
                ('Preciso fazer dieta restritiva?', 'Não! Trabalhamos com reeducação alimentar flexível, adaptada à sua rotina e preferências.'),
                ('Atende convênio?', 'Atendemos particular e alguns convênios. Entre em contato para verificar o seu.'),
                ('Como é a primeira consulta?', 'Avaliação completa: histórico, exames, rotina, preferências. Montamos o plano juntos.'),
            ],
            'psicologos': [
                ('Como funciona a terapia?', 'Encontros semanais de 50min, espaço seguro e sigiloso para você se expressar.'),
                ('Quantas sessões vou precisar?', 'Varia conforme sua demanda. Avaliamos juntos a cada sessão.'),
                ('O sigilo é garantido?', 'Sim, sigilo profissional absoluto conforme código de ética.'),
            ],
        }
        faqs = faqs_padrao.get(lead.nicho.lower(), [
            ('Dúvida 1', 'Resposta 1'),
            ('Dúvida 2', 'Resposta 2'),
        ])
    
    items = ""
    for i, (pergunta, resposta) in enumerate(faqs):
        items += f"""
        <details class="faq-item">
            <summary>{pergunta}</summary>
            <p>{resposta}</p>
        </details>"""
    
    return f'''
<section class="faq" id="faq">
    <div class="container">
        <h2>Perguntas Frequentes</h2>
        <div class="faq-list">{items}</div>
    </div>
</section>'''


def generate_contato(lead: Lead, conteudo: Dict) -> str:
    endereco = lead.endereco or conteudo.get('endereco', '')
    horario = conteudo.get('horario', 'Seg a Sex: 8h-18h | Sáb: 8h-12h')
    mapa_embed = f"https://www.google.com/maps/embed/v1/place?key=SUA_CHAVE&q={lead.nome.replace(' ', '+')}+{lead.cidade}"
    
    return f'''
<section class="contato" id="contato">
    <div class="container">
        <h2>Entre em Contato</h2>
        <div class="contato-grid">
            <div class="contato-info">
                <h3>{lead.nome}</h3>
                <p><strong>📍 Endereço:</strong> {endereco}</p>
                <p><strong>📞 Telefone:</strong> <a href="tel:{lead.telefone}">{lead.telefone}</a></p>
                <p><strong>💬 WhatsApp:</strong> <a href="https://wa.me/{lead.whatsapp}" target="_blank">{lead.whatsapp}</a></p>
                <p><strong>📧 E-mail:</strong> <a href="mailto:{lead.email}">{lead.email}</a></p>
                <p><strong>🕐 Horário:</strong> {horario}</p>
            </div>
            <div class="contato-mapa">
                <iframe src="{mapa_embed}" width="100%" height="300" style="border:0;border-radius:12px;" allowfullscreen loading="lazy"></iframe>
            </div>
        </div>
        <form class="contato-form" action="https://formspree.io/f/SEU_ID" method="POST">
            <input type="hidden" name="_next" value="{_public_url(lead.slug)}obrigado.html">
            <div class="form-row">
                <input type="text" name="nome" placeholder="Seu nome" required>
                <input type="tel" name="telefone" placeholder="WhatsApp/Telefone" required>
            </div>
            <input type="email" name="email" placeholder="E-mail" required>
            <textarea name="mensagem" placeholder="Como podemos ajudar?" rows="4" required></textarea>
            <button type="submit" class="btn btn-primary">Enviar Mensagem</button>
        </form>
    </div>
</section>'''


def generate_footer(lead: Lead) -> str:
    return f'''
<footer class="footer">
    <div class="container">
        <div class="footer-grid">
            <div class="footer-brand">
                <h3>{lead.nome}</h3>
                <p>Excellence em {lead.nicho} na região de {lead.cidade}.</p>
            </div>
            <nav class="footer-links">
                <h4>Links Rápidos</h4>
                <ul>
                    <li><a href="#sobre">Sobre</a></li>
                    <li><a href="#servicos">Serviços</a></li>
                    <li><a href="#depoimentos">Depoimentos</a></li>
                    <li><a href="#contato">Contato</a></li>
                </ul>
            </nav>
            <div class="footer-social">
                <h4>Conecte-se</h4>
                <a href="https://wa.me/{lead.whatsapp}" target="_blank" class="social-link">WhatsApp</a>
                <a href="mailto:{lead.email}" class="social-link">E-mail</a>
            </div>
        </div>
        <div class="footer-bottom">
            <p>&copy; {datetime.now().year} {lead.nome}. Todos os direitos reservados.</            <p>Desenvolvido por <a href="https://iabotz.online" target="_blank">IA Botz</a></p>
        </div>
    </div>
</footer>'''


def generate_page_html(lead: Lead, conteudo: Dict) -> str:
    css_vars = generate_css_variables(conteudo.get('cores', {}))
    
    nicho = lead.nicho or "Serviços"
    cidade = lead.cidade or "Sua Cidade"
    
    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{lead.nome} - {nicho.title()} em {cidade}</title>
<meta name="description" content="{lead.nome} - {nicho.title()} em {cidade}. {conteudo.get('meta_description', 'Atendimento humanizado e especializado. Agende sua consulta.')}">
<meta name="theme-color" content="{conteudo.get('cores', {}).get('primary', '#1e40af')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{css_vars}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-body);background:var(--color-bg);color:var(--color-text);line-height:1.6}}
.container{{max-width:1200px;margin:0 auto;padding:0 20px}}
a{{color:var(--color-primary);text-decoration:none}}
a:hover{{text-decoration:underline}}
img{{max-width:100%;height:auto;display:block}}
.btn{{display:inline-flex;align-items:center;gap:8px;padding:14px 28px;border-radius:var(--radius-md);font-weight:600;font-size:1rem;transition:all .2s;border:none;cursor:pointer}}
.btn-primary{{background:var(--color-primary);color:#fff}}
.btn-primary:hover{{background:#1d4ed8;transform:translateY(-2px);box-shadow:var(--shadow-md)}}
.btn-secondary{{background:var(--color-card);color:var(--color-primary);border:2px solid var(--color-primary)}}
.btn-secondary:hover{{background:var(--color-primary);color:#fff}}
.btn-outline{{background:transparent;color:var(--color-primary);border:2px solid var(--color-primary)}}
.btn-outline:hover{{background:var(--color-primary);color:#fff}}
.section{{padding:80px 0}}
h2{{font-size:clamp(1.75rem,4vw,2.5rem);font-weight:700;color:var(--color-secondary);margin-bottom:8px}}
h3{{font-size:1.25rem;font-weight:600;color:var(--color-secondary)}}
p{{color:var(--color-text);margin-bottom:16px}}

/* Hero */
.hero{{min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;background:linear-gradient(135deg,var(--color-primary) 0%,#3b82f6 100%);color:#fff;padding:100px 20px}}
.hero h1{{font-size:clamp(2rem,5vw,3.5rem);font-weight:700;margin-bottom:16px;line-height:1.2}}
.hero p{{font-size:clamp(1rem,2vw,1.25rem);opacity:.9;margin-bottom:32px;max-width:600px;margin-left:auto;margin-right:auto}}
.cta-group{{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}}

/* Sections */
.section-title{{text-align:center;margin-bottom:48px}}
.section-title h2::after{{content:'';display:block;width:60px;height:4px;background:var(--color-primary);margin:12px auto 0;border-radius:2px}}

/* Grid */
.grid{{display:grid;gap:24px}}
.grid-2{{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}}
.grid-3{{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}}
.grid-4{{grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}}

/* Cards */
.card{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:32px;transition:all .3s}}
.card:hover{{transform:translateY(-4px);box-shadow:var(--shadow-lg)}}
.card-icon{{font-size:2.5rem;margin-bottom:16px}}

/* Serviços */
.servicos-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}}
.servico-card{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:32px;text-align:center;transition:all .3s}}
.servico-card:hover{{transform:translateY(-4px);box-shadow:var(--shadow-lg)}}
.servico-icon{{font-size:3rem;margin-bottom:16px}}
.servico-card h3{{margin-bottom:12px}}
.servico-card p{{color:var(--color-muted);margin-bottom:20px}}
.servico-cta{{font-weight:600;color:var(--color-primary);font-size:.9rem}}

/* Depoimentos */
.depoimentos-carousel{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}}
.depoimento-card{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:32px}}
.depoimento-stars{{font-size:1.2rem;margin-bottom:12px}}
.depoimento-texto{{font-style:italic;color:var(--color-text);margin-bottom:16px}}
.depoimento-autor{{display:flex;align-items:center;gap:12px}}
.depoimento-autor img{{width:48px;height:48px;border-radius:50%;object-fit:cover}}

/* FAQ */
.faq-list{{max-width:800px;margin:0 auto}}
.faq-item{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-md);margin-bottom:12px;overflow:hidden}}
.faq-item summary{{padding:20px 24px;font-weight:600;cursor:pointer;list-style:none}}
.faq-item summary::-webkit-details-marker{{display:none}}
.faq-item summary::after{{content:'+';float:right;transition:transform .3s}}
.faq-item[open] summary::after{{transform:rotate(45deg)}}
.faq-item p{{padding:0 24px 20px;color:var(--color-muted)}}

/* Contato */
.contato-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:48px;align-items:start}}
.contato-info h3{{margin-bottom:24px}}
.contato-info p{{margin-bottom:12px;display:flex;align-items:center;gap:12px}}
.contato-form{{background:var(--color-card);border:1px solid var(--color-border);border-radius:var(--radius-lg);padding:32px}}
.form-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.contato-form input,.contato-form textarea{{width:100%;padding:14px 16px;border:1px solid var(--color-border);border-radius:var(--radius-md);font-size:1rem;font-family:inherit;margin-bottom:16px;transition:border .2s}}
.contato-form input:focus,.contato-form textarea:focus{{outline:none;border-color:var(--color-primary);box-shadow:0 0 0 3px rgba(30,64,175,.15)}}
.contato-form button{{width:100%;margin-top:8px}}

/* Footer */
.footer{{background:var(--color-secondary);color:#fff;padding:60px 0 24px}}
.footer-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:40px;margin-bottom:40px}}
.footer-brand h3{{color:#fff;margin-bottom:12px}}
.footer-brand p{{color:#94a3b8}}
.footer-links h4,.footer-social h4{{color:#fff;margin-bottom:16px}}
.footer-links ul{{list-style:none}}
.footer-links li{{margin-bottom:8px}}
.footer-links a{{color:#94a3b8;transition:color .2s}}
.footer-links a:hover{{color:#fff}}
.social-link{{display:inline-block;color:#94a3b8;margin-right:16px;transition:color .2s}}
.social-link:hover{{color:#fff}}
.footer-bottom{{border-top:1px solid rgba(255,255,255,.1);padding-top:24px;text-align:center;color:#64748b;font-size:.9rem}}
.footer-bottom a{{color:var(--color-primary)}}

/* Responsive */
@media(max-width:768px){{
    .hero{{min-height:auto;padding:60px 20px}}
    .cta-group{{flex-direction:column;align-items:center}}
    .btn{{width:100%;justify-content:center}}
    .form-row{{grid-template-columns:1fr}}
    .footer-grid{{grid-template-columns:1fr}}
    .contato-grid{{grid-template-columns:1fr}}
}}

/* Utils */
.sr-only{{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}}
.skip-link{{position:absolute;top:-40px;left:0;background:var(--color-primary);color:#fff;padding:8px 16px;z-index:100;transition:top .3s}}
.skip-link:focus{{top:0}}
</style>
</head>
<body>
<a href="#main" class="skip-link">Pular para o conteúdo principal</a>

{generate_hero(lead, conteudo)}
{generate_sobre(lead, conteudo)}
{generate_servicos(lead, conteudo)}
{generate_depoimentos(lead, conteudo)}
{generate_faq(lead, conteudo)}
{generate_contato(lead, conteudo)}
{generate_footer(lead)}

<script>
// Smooth scroll
document.querySelectorAll('a[href^="#"]').forEach(a=>{{
    a.addEventListener('click',e=>{{
        const id=a.getAttribute('href');
        if(id==='#')return;
        const el=document.querySelector(id);
        if(el){{e.preventDefault();el.scrollIntoView({{behavior:'smooth'}});}}
    }});
}});

// FAQ
document.querySelectorAll('.faq-item').forEach(item=>{{
    item.addEventListener('toggle',()=>{{}});
}});

// Form submit
document.querySelector('.contato-form')?.addEventListener('submit',async e=>{{
    e.preventDefault();
    const form=e.target;
    const btn=form.querySelector('button[type="submit"]');
    const original=btn.textContent;
    btn.textContent='Enviando...';
    btn.disabled=true;
    try{{
        const res=await fetch(form.action,{{
            method:'POST',
            body:new FormData(form),
            headers:{{'Accept':'application/json'}}
        }});
        if(res.ok){{alert('Mensagem enviada! Entraremos em contato em breve.');form.reset();}}
        else{{alert('Erro ao enviar. Tente novamente ou chame no WhatsApp.');}}
    }}catch{{alert('Erro de conexão. Tente no WhatsApp.');}}
    finally{{btn.textContent=original;btn.disabled=false;}}
}});
</script>
</body>
</html>'''
    return html


async def redesign_lead(lead: Lead, conteudo_extra: Dict = None) -> Dict:
    """Executa redesign completo de um lead"""
    print(f"🎨 Redesenhando: {lead.nome}")
    
    # Extrai conteúdo (em produção, usar Playwright)
    conteudo = extract_content_from_site(lead.site_atual)
    if conteudo_extra:
        conteudo.update(conteudo_extra)
    
    # Gera HTML
    html = generate_page_html(lead, conteudo)
    
    # Salva arquivos
    site_dir = BASE_DIR / "sites" / lead.slug
    site_dir.mkdir(parents=True, exist_ok=True)
    
    # index.html
    (site_dir / "index.html").write_text(html, encoding='utf-8')
    
    # proposta.html (capa para e-mail)
    proposta_html = generate_proposta_html(lead, conteudo)
    (site_dir / "proposta.html").write_text(proposta_html, encoding='utf-8')
    
    # editor.html
    editor_html = generate_editor_html(lead, conteudo)
    (site_dir / "editor.html").write_text(editor_html, encoding='utf-8')
    
    # comparador.html
    comparador_html = generate_comparador_html(lead, conteudo)
    (site_dir / "comparador.html").write_text(comparador_html, encoding='utf-8')
    
    # assets (copiar se existirem)
    assets_src = BASE_DIR / "skills" / "redesign-premium" / "references" / "assets"
    if assets_src.exists():
        assets_dst = site_dir / "assets"
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)
    
    print(f"   ✅ Site gerado em: {site_dir}")
    return {
        'slug': lead.slug,
        'site_dir': str(site_dir),
        'url': _public_url(lead.slug),
        'proposta_url': _public_url(lead.slug) + 'proposta.html'
    }


def generate_proposta_html(lead: Dict, conteudo: Dict) -> str:
    """Gera página-capa para proposta (antes/depois)"""
    cores = conteudo.get('cores', {'primary': '#1e40af'})
    css_vars = generate_css_variables(cores)
    
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nova versão do site - {conteudo.get('nome', 'Cliente')}</title>
<style>
{css_vars}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f8fafc;color:#1e293b;line-height:1.6}}
.container{{max-width:1000px;margin:0 auto;padding:40px 20px}}
.header{{text-align:center;padding:40px 0;border-bottom:1px solid #e2e8f0;margin-bottom:40px}}
.header h1{{font-size:2rem;color:#1e40af;margin-bottom:8px}}
.before-after{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:32px 0}}
@media(max-width:768px){{.before-after{{grid-template-columns:1fr}}}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}}
.card-header{{padding:16px;font-weight:600;text-align:center}}
.card-header.old{{background:#fef2f2;color:#dc2626;border-bottom:2px solid #fecaca}}
.card-header.new{{background:#f0fdf4;color:#059669;border-bottom:2px solid #bbf7d0}}
.card-img{{aspect-ratio:16/10;background:#f1f5f9;display:flex;align-items:center;justify-content:center;color:#64748b;font-size:.85rem}}
.features{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;margin:32px 0}}
.feature{{display:flex;align-items:flex-start;gap:12px;padding:16px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0}}
.feature-icon{{width:40px;height:40px;background:#1e40af;border-radius:10px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:1.25rem;flex-shrink:0}}
.feature-text h3{{font-size:.95rem;font-weight:600;margin-bottom:4px}}
.feature-text p{{font-size:.85rem;color:#64748b;margin:0}}
.cta{{text-align:center;margin-top:40px;padding-top:32px;border-top:1px solid #e2e8f0}}
.btn{{display:inline-block;background:#1e40af;color:#fff;padding:16px 32px;border-radius:10px;font-weight:600;text-decoration:none;transition:background .2s}}
.btn:hover{{background:#1e3a8a}}
.footer{{text-align:center;padding-top:32px;border-top:1px solid #e2e8f0;color:#64748b;font-size:.9rem}}
</style>
</head>
<body>
<div class="container">
<header class="header">
<h1>Nova versão do site: <strong>{conteudo.get('nome', 'Cliente')}</strong></h1>
<p>Antes & Depois — comparação lado a lado</p>
</header>

<div class="before-after">
<div class="card">
<div class="card-header old">🔴 Site Atual</div>
<div class="card-img">[Screenshot do site antigo]</div>
</div>
<div class="card">
<div class="card-header new">🟢 Nova Versão</div>
<div class="card-img">[Screenshot do novo site]</div>
</div>
</div>

<div class="features">
<div class="feature"><span class="feature-icon">📱</span><div class="feature-text"><h3>Mobile-first real</h3><p>Layout fluido, toque otimizado, CTA sempre visível</p></div></div>
<div class="feature"><span class="feature-icon">⚡</span><div class="feature-text"><h3>Carregamento <2s</h3><p>CSS/JS crítico inline, imagens WebP lazy-load</p></div></div>
<div class="feature"><span class="feature-icon">🔍</span><div class="feature-text"><h3>SEO técnico completo</h3><p>Schema.org, meta tags, heading hierarchy, sitemap</p></div></div>
<div class="feature"><span class="feature-icon">💬</span><div class="feature-text"><h3>WhatsApp one-click</h3><p>CTA flutuante + formulário + telefone visível</p></div></div>
</div>

<div class="cta">
<a class="btn" href="https://wa.me/5511999990000" target="_blank">Ver site no ar →</a>
</div>

<div class="footer">
Feito com dedicação para <strong>{conteudo.get('nome', 'Cliente')}</strong> pela IA Botz
</div>
</div>
</body>
</html>'''


def generate_editor_html(lead: Dict, conteudo: Dict) -> str:
    """Editor visual para ajustes manuais"""
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Editor Visual - {conteudo.get('nome', 'Cliente')}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f1f5f9;height:100vh;display:flex}}
.toolbar{{width:320px;background:#fff;border-right:1px solid #e2e8f0;padding:20px;overflow-y:auto;position:fixed;height:100vh;left:0;top:0;z-index:100}}
.toolbar h2{{font-size:1.25rem;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid #e2e8f0}}
.toolbar-section{{margin-bottom:24px}}
.toolbar-section h3{{font-size:.85rem;text-transform:uppercase;color:#64748b;margin-bottom:12px;letter-spacing:.5px}}
.color-picker{{display:flex;gap:8px;margin-bottom:8px}}
.color-btn{{width:36px;height:36px;border-radius:8px;border:2px solid transparent;cursor:pointer;transition:border .2s}}
.color-btn.active{{border-color:#1e40af}}
.color-btn:hover{{transform:scale(1.1)}}
.btn{{width:100%;padding:10px 16px;border-radius:8px;font-weight:600;margin-top:8px;cursor:pointer;border:none;font-size:.9rem}}
.btn-primary{{background:#1e40af;color:#fff}}
.btn-primary:hover{{background:#1e3a8a}}
.btn-secondary{{background:#f1f5f9;color:#1e40af;border:1px solid #e2e8f0}}
iframe{{flex:1;border:none;background:#fff}}
@media(max-width:768px){{.toolbar{{position:fixed;bottom:0;left:0;right:0;width:auto;height:auto;max-height:60vh;border-top:1px solid #e2e8f0;border-right:none}}}}
</style>
</head>
<body>
<div class="toolbar">
<h2>✏️ Editor Visual</h2>
<div class="toolbar-section">
<h3>Cores da Marca</h3>
<div class="color-picker">
<button class="color-btn" style="background:#1e40af" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#059669" data-var="--color-accent" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#dc2626" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#7c3aed" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#ea580c" data-var="--color-primary" onclick="setColor(this)"></button>
<button class="color-btn" style="background:#0891b2" data-var="--color-primary" onclick="setColor(this)"></button>
</div>
<input type="color" id="color-primary" value="#1e40af" onchange="applyColor('--color-primary', this.value)">
<input type="color" id="color-accent" value="#059669" onchange="applyColor('--color-accent', this.value)">
</div>
<div class="toolbar-section">
<h3>Tipografia</h3>
<select onchange="applyFont('heading', this.value)"><option value="Inter,system-ui,sans-serif">Inter (padrão)</option><option value="Poppins,system-ui,sans-serif">Poppins</option><option value="Roboto,system-ui,sans-serif">Roboto</option><option value="Montserrat,system-ui,sans-serif">Montserrat</option></select>
<select onchange="applyFont('body', this.value)"><option value="Inter,system-ui,sans-serif">Inter (padrão)</option><option value="DM Sans,system-ui,sans-serif">DM Sans</option><option value="Open Sans,system-ui,sans-serif">Open Sans</option></select>
</div>
<div class="toolbar-section">
<h3>Ações</h3>
<button class="btn btn-primary" onclick="exportHTML()">💾 Exportar HTML</button>
<button class="btn btn-secondary" onclick="resetStyles()">🔄 Resetar</button>
</div>
</div>
<iframe id="preview" src="index.html"></iframe>
<script>
function setColor(btn){{
    document.querySelectorAll('.color-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    const varName=btn.dataset.var;
    const color=btn.style.backgroundColor;
    applyColor(varName, color);
}}
function applyColor(varName, color){{
    document.documentElement.style.setProperty(varName, color);
    document.getElementById('preview').contentDocument.documentElement.style.setProperty(varName, color);
}}
function applyFont(type, font){{
    const varName=type==='heading'?'--font-heading':'--font-body';
    applyColor(varName, font);
}}
function applyColor(varName, value){{
    document.documentElement.style.setProperty(varName, value);
    const iframe=document.getElementById('preview');
    iframe.contentDocument.documentElement.style.setProperty(varName, value);
}}
function exportHTML(){{
    const html=document.getElementById('preview').contentDocument.documentElement.outerHTML;
    const blob=new Blob([html],{{type:'text/html'}});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;a.download='index.html';a.click();
    URL.revokeObjectURL(url);
}}
function resetStyles(){{
    document.documentElement.style.cssText='';
    const iframe=document.getElementById('preview');
    iframe.contentDocument.documentElement.style.cssText='';
    iframe.src=iframe.src;
}}
</script>
</body>
</html>'''


def generate_comparador_html(lead: Dict, conteudo: Dict) -> str:
    """Slider antes/depois"""
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparador - {conteudo.get('nome', 'Cliente')}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#f8fafc;min-height:100vh}}
.container{{max-width:1200px;margin:0 auto;padding:20px}}
h1{{text-align:center;margin:32px 0;font-size:clamp(1.5rem,4vw,2.5rem);color:#1e293b}}
.tabs{{display:flex;justify-content:center;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.tab{{padding:12px 24px;border:1px solid #e2e8f0;background:#fff;border-radius:8px;cursor:pointer;font-weight:500;transition:all .2s}}
.tab.active{{background:#1e40af;color:#fff;border-color:#1e40af}}
.comparison{{position:relative;height:600px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}}
@media(max-width:768px){{.comparison{{height:400px}}}}
.view{{position:absolute;top:0;left:0;width:100%;height:100%;overflow:hidden}}
.view.old{{z-index:1}}
.view.new{{z-index:2;clip-path:polygon(50% 0,100% 0,100% 100%,50% 100%)}}
.handle{{position:absolute;top:0;bottom:0;width:4px;background:#1e40af;left:50%;transform:translateX(-50%);z-index:10;cursor:ew-resize}}
.handle::before{{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:32px;height:32px;background:#1e40af;border-radius:50%;opacity:.8;display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px}}
.handle::after{{content:'';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:48px;height:48px;border:2px solid #1e40af;border-radius:50%;opacity:.3}}
iframe{{width:100%;height:100%;border:none}}
@media(max-width:768px){{.comparison{{height:350px}}h1{{font-size:1.5rem}}}}
</style>
</head>
<body>
<div class="container">
<h1>📊 Comparador: Antes vs Depois</h1>
<div class="tabs">
<button class="tab active" onclick="showTab('split')">📱 Slider</button>
<button class="tab" onclick="showTab('side')">📐 Lado a Lado</button>
<button class="tab" onclick="showTab('old')">🔴 Antigo</button>
<button class="tab" onclick="showTab('new')">🟢 Novo</button>
</div>
<div class="comparison" id="comparison">
<div class="view old"><iframe src="http://webcache.googleusercontent.com/search?q=cache:{conteudo.get('site_atual', '')}"></iframe></div>
<div class="view new"><iframe src="index.html"></iframe></div>
<div class="handle" id="handle"></div>
</div>
</div>
<script>
let isDragging=false;
const comparison=document.getElementById('comparison');
const handle=document.getElementById('handle');
const newView=comparison.querySelector('.view.new');
function showTab(tab){{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    event.target.classList.add('active');
    const oldView=comparison.querySelector('.view.old');
    const newView=comparison.querySelector('.view.new');
    const handle=comparison.querySelector('.handle');
    if(tab==='split'){{oldView.style.display='block';newView.style.display='block';handle.style.display='block';newView.style.clipPath='polygon(50% 0,100% 0,100% 100%,50% 100%)';}}
    else if(tab==='side'){{oldView.style.display='block';newView.style.display='block';handle.style.display='none';oldView.style.width='50%';newView.style.width='50%';newView.style.clipPath='none';}}
    else if(tab==='old'){{oldView.style.display='block';newView.style.display='none';handle.style.display='none';}}
    else if(tab==='new'){{oldView.style.display='none';newView.style.display='block';handle.style.display='none';newView.style.clipPath='none';}}
}}
handle.addEventListener('mousedown',e=>{{isDragging=true;}});
document.addEventListener('mousemove',e=>{{if(!isDragging)return;const rect=comparison.getBoundingClientRect();let x=e.clientX-rect.left;x=Math.max(0,Math.min(x,rect.width));newView.style.clipPath=`polygon(${{x}}px 0,${{rect.width}}px 0,${{rect.width}}px ${{rect.height}}px,${{x}}px ${{rect.height}}px)`;handle.style.left=`${{x}}px`;}});
document.addEventListener('mouseup',()=>{{isDragging=false;}});
handle.addEventListener('touchstart',e=>{{isDragging=true;}},{{passive:true}});
document.addEventListener('touchmove',e=>{{if(!isDragging)return;const rect=comparison.getBoundingClientRect();let x=e.touches[0].clientX-rect.left;x=Math.max(0,Math.min(x,rect.width));newView.style.clipPath=`polygon(${{x}}px 0,${{rect.width}}px 0,${{rect.width}}px ${{rect.height}}px,${{x}}px ${{rect.height}}px)`;handle.style.left=`${{x}}px`;}},{{passive:true}});
document.addEventListener('touchend',()=>{{isDragging=false;}});
</script>
</body>
</html>'''


# ============================================================
# MAIN
# ============================================================

async def main():
    if len(sys.argv) < 2:
        print("Uso: python3 redesign.py <slug|todos>")
        sys.exit(1)

    target = sys.argv[1]
    slugs = list_slugs_for_redesign(target)

    if not slugs:
        print("⚠️  Nenhum lead elegível para redesign (status 'novo' ou slug inexistente)")
        sys.exit(1)

    print(f"\n🎨 Iniciando redesign de {len(slugs)} site(s)...\n")

    for slug in slugs:
        lead = load_lead(slug)
        if not lead:
            print(f"❌ Lead não encontrado: {slug}")
            continue

        await redesign_lead(lead)
        mark_redesigned(slug)
        print(f"✅ Status → redesenhado: {slug}")

    print("\n🎉 Redesign concluído!")
    print("💡 Próximo: publicar no painel ou ./prospector publicar")


if __name__ == "__main__":
    asyncio.run(main())

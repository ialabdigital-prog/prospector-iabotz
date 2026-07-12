#!/usr/bin/env python3
"""
Prospector Playwright - Google Maps Scraper para prospecção de leads
Roda no servidor (headless), não depende do Chrome do usuário
"""

import asyncio
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:
    print("Instale: pip install playwright && playwright install chromium")
    sys.exit(1)

# ============================================================
# CONFIG & PATHS
# ============================================================

BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "prospector-config.json"
LEADS_FILE = BASE_DIR / "leads.md"
SELECTORS_FILE = Path(__file__).parent / "selectors-maps.json"
STATE_FILE = BASE_DIR / "playwright-state.json"


def load_config() -> Dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def load_selectors() -> Dict:
    if SELECTORS_FILE.exists():
        return json.loads(SELECTORS_FILE.read_text())
    return get_default_selectors()


def get_default_selectors() -> Dict:
    return {
        "maps": {
            "search_url": "https://www.google.com/maps/search/{query}",
            "result_cards": '//div[contains(@class, "Nv2PK")]',
            "card_name": './/div[contains(@class, "qBF1D")]//span',
            "card_rating": './/span[contains(@aria-label, "estrelas") or contains(@aria-label, "stars")]',
            "card_reviews": './/span[contains(@aria-label, "avalia") or contains(@aria-label, "review")]',
            "card_website_button": './/button[contains(@aria-label, "Site") or contains(@aria-label, "Website")]',
            "card_phone_button": './/button[contains(@aria-label, "Telefone") or contains(@aria-label, "Phone")]',
            "card_address": './/div[contains(@class, "W4Efsd")]//span[contains(@class, "UsdlK")]',
        },
        "place_detail": {
            "name": '//h1[contains(@class, "DUwDvf")]',
            "rating": '//span[contains(@class, "F7nice")]',
            "reviews_count": '//button[contains(@class, "HHrUdb")]',
            "address": '//button[contains(@data-item-id, "address")]//div[contains(@class, "Io6YTe")]',
            "phone": '//button[contains(@data-item-id, "phone")]',
            "website": '//a[contains(@data-item-id, "authority")]',
            "website_button": '//button[contains(@data-item-id, "authority")]',
        },
        "scroll_config": {
            "max_cards": 50,
            "scroll_pause_ms": 1500,
            "no_new_cards_threshold": 3
        },
        "wait_times": {
            "page_load": 3000,
            "card_click": 1500,
            "site_load": 5000
        }
    }


# ============================================================
# UTILITÁRIOS
# ============================================================

def slugify(text: str) -> str:
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE).strip().lower()
    text = re.sub(r'[-\s]+', '-', text)
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i').replace('ó', 'o').replace('ô', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c').replace('ñ', 'n')
    return text


def normalize_phone(phone: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('55'):
        return digits
    if len(digits) == 10:  # DDD + 8 dígitos (fixo antigo)
        return '55' + digits
    if len(digits) == 11:  # DDD + 9 dígitos (celular)
        return '55' + digits
    if len(digits) >= 10:
        return '55' + digits[-11:]
    return digits


def extract_emails(text: str) -> List[str]:
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(pattern, text)
    # Filtrar genéricos
    filtered = []
    for e in emails:
        if not any(g in e.lower() for g in ['noreply', 'no-reply', 'donotreply', 'exemplo', 'example', 'teste', 'test']):
            filtered.append(e)
    return filtered


def is_third_party_directory(url: str) -> bool:
    third_party_domains = [
        'localtreino.com', 'acheioprofissional.com', 'guiamais.com.br',
        'listamais.com.br', 'telelistas.net', '11880.com', 'apontador.com.br',
        'wikidot.com', 'google.com/sites', 'sites.google.com', 'wixsite.com',
        'wordpress.com', 'blogspot.com', 'weebly.com', 'jimdo.com'
    ]
    domain = urlparse(url).netloc.lower().replace('www.', '')
    return any(tp in domain for tp in third_party_domains)


async def analyze_website_quality(page: Page, url: str) -> Dict:
    """Analisa qualidade do site - retorna dict com problemas encontrados"""
    result = {
        'ruim': False,
        'motivos': [],
        'emails': [],
        'whatsapp': '',
        'responsivo': True,
        'tem_cta': False,
        'dominio_gratis': False,
        'layout_datado': False
    }
    
    try:
        # Navegar para o site
        response = await page.goto(url, wait_until='networkidle', timeout=15000)
        if not response or response.status >= 400:
            result['motivos'].append(f"Site inacessível (HTTP {response.status if response else 'timeout'})")
            result['ruim'] = True
            return result
        
        await page.wait_for_timeout(2000)
        
        # 1. Extrair e-mails
        content = await page.content()
        emails = extract_emails(content)
        result['emails'] = emails
        
        # 2. Extrair WhatsApp
        wa_links = await page.query_selector_all('a[href*="wa.me"], a[href*="api.whatsapp.com"], a[href*="whatsapp.com"]')
        for link in wa_links:
            href = await link.get_attribute('href')
            if href:
                match = re.search(r'(?:wa\.me/|phone=)(\d+)', href)
                if match:
                    result['whatsapp'] = normalize_phone(match.group(1))
                    break
        
        # 3. Verificar responsividade (viewport mobile)
        await page.set_viewport_size({'width': 375, 'height': 667})
        await page.wait_for_timeout(1000)
        body_width = await page.evaluate('document.body.scrollWidth')
        if body_width > 400:
            result['responsivo'] = False
            result['motivos'].append("Não responsivo (quebra no mobile)")
        
        # Voltar para desktop
        await page.set_viewport_size({'width': 1366, 'height': 768})
        await page.wait_for_timeout(500)
        
        # 4. Verificar CTA acima da dobra
        cta_selectors = [
            'a[href*="wa.me"]', 'a[href*="whatsapp"]', 'button:has-text("WhatsApp")',
            'a:has-text("Agendar")', 'button:has-text("Agendar")',
            'a[href*="calendly"]', 'a[href*="agenda"]', 'button:has-text("Contato")'
        ]
        for sel in cta_selectors:
            elem = await page.query_selector(sel)
            if elem:
                box = await elem.bounding_box()
                if box and box['y'] < 800:  # Above the fold aproximado
                    result['tem_cta'] = True
                    break
        
        if not result['tem_cta']:
            result['motivos'].append("Sem CTA claro de agendamento/contato acima da dobra")
        
        # 5. Domínio gratuito / plataforma alheia
        domain = urlparse(url).netloc.lower().replace('www.', '')
        free_indicators = ['sites.google.com', 'wixsite.com', 'wordpress.com', 'blogspot.com',
                           '.webflow.io', '.vercel.app', '.netlify.app', '.github.io',
                           'googlepages.com', 'weebly.com', 'jimdo.com']
        if any(fi in domain for fi in free_indicators):
            result['dominio_gratis'] = True
            result['motivos'].append(f"Domínio gratuito/plataforma alheia ({domain})")
        
        # 6. Layout datado (heurística simples)
        # Verificar fontes de sistema, ausência de CSS moderno, imagens sem srcset
        has_modern_css = await page.evaluate("""
            () => {
                const sheets = Array.from(document.styleSheets);
                return sheets.some(s => {
                    try { return s.cssRules && s.cssRules.length > 0; } catch { return false; }
                });
            }
        """)
        # Verificar se usa fontes do sistema apenas
        font_families = await page.evaluate("""
            () => Array.from(new Set(
                Array.from(document.querySelectorAll('*'))
                    .map(el => getComputedStyle(el).fontFamily)
                    .filter(f => f && !f.includes('system') && !f.includes('Arial') && !f.includes('sans-serif'))
            ))
        """)
        
        if not font_families or len(font_families) == 0:
            result['layout_datado'] = True
            result['motivos'].append("Layout datado (fontes de sistema, aparência template antigo)")
        
        # 7. Conteúdo desorganizado
        h1_count = await page.evaluate("document.querySelectorAll('h1').length")
        h2_count = await page.evaluate("document.querySelectorAll('h2').length")
        if h1_count == 0 and h2_count < 2:
            result['motivos'].append("Conteúdo desorganizado: sem hierarquia de títulos (h1/h2)")
        
        # 8. Prova social no site
        has_testimonials = await page.evaluate("""
            () => {
                const text = document.body.innerText.toLowerCase();
                return text.includes('depoimento') || text.includes('avaliação') || 
                       text.includes('review') || text.includes('testemunho') ||
                       text.includes('google reviews') || text.includes('avaliações');
            }
        """)
        if not has_testimonials:
            result['motivos'].append("Sem prova social no site (nenhum depoimento/avaliação)")
        
        # Determinar se site é ruim (2+ problemas)
        problemas = len([m for m in result['motivos'] if m])
        result['ruim'] = problemas >= 2
        
    except Exception as e:
        result['motivos'].append(f"Erro ao analisar site: {str(e)}")
        result['ruim'] = True
    
    return result


# ============================================================
# DATA CLASS
# ============================================================

@dataclass
class Lead:
    slug: str = ""
    nome: str = ""
    nota: float = 0.0
    avaliacoes: int = 0
    email: str = ""
    telefone: str = ""
    whatsapp: str = ""
    site_atual: str = ""
    motivo: str = ""
    cidade: str = ""
    nicho: str = ""
    endereco: str = ""
    status: str = "novo"
    url_nova: str = ""
    data_prospeccao: str = ""
    
    def __post_init__(self):
        if not self.slug and self.nome and self.cidade:
            self.slug = slugify(f"{self.nome}-{self.cidade}")
        if not self.data_prospeccao:
            self.data_prospeccao = datetime.now().isoformat()


# ============================================================
# SCRAPER PRINCIPAL
# ============================================================

class MapsScraper:
    def __init__(self, config: Dict):
        self.config = config
        self.playwright_config = config.get('playwright', {})
        self.prospeccao_config = config.get('prospeccao', {})
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.selectors = load_selectors()
        self.leads_existentes = self._carregar_leads_existentes()

    def _carregar_leads_existentes(self) -> Set[str]:
        slugs = set()
        if LEADS_FILE.exists():
            content = LEADS_FILE.read_text()
            for line in content.split('\n'):
                if '|' in line and not line.startswith('| #') and not line.startswith('|---'):
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3:
                        slug = slugify(parts[1])
                        slugs.add(slug)
        return slugs

    async def init_browser(self):
        """Inicializa browser Playwright com config stealth"""
        pw = await async_playwright().start()
        
        # Carregar estado persistente se existir
        storage_state = None
        if STATE_FILE.exists():
            storage_state = str(STATE_FILE)
        
        self.browser = await pw.chromium.launch(
            headless=self.playwright_config.get('headless', True),
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        self.context = await self.browser.new_context(
            storage_state=storage_state,
            user_agent=self.playwright_config.get('user_agent', 
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            viewport=self.playwright_config.get('viewport', {'width': 1366, 'height': 768}),
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
            permissions=['geolocation']
        )
        
        # Stealth: remover navigator.webdriver
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.playwright_config.get('timeout_ms', 30000))

    async def save_state(self):
        """Salva estado (cookies, localStorage) para próxima execução"""
        if self.context:
            await self.context.storage_state(path=str(STATE_FILE))

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def search_maps(self, nicho: str, cidade: str) -> List[Dict]:
        """Busca no Google Maps e retorna lista de cards básicos"""
        query = f"{nicho} em {cidade}".replace(' ', '+')
        url = self.selectors['maps']['search_url'].format(query=query)
        
        print(f"🔍 Buscando: {nicho} em {cidade}")
        await self.page.goto(url, wait_until='networkidle')
        await self.page.wait_for_timeout(self.selectors['wait_times']['page_load'])
        
        cards_data = []
        seen_names = set()
        no_new_cards = 0
        max_cards = self.selectors['scroll_config']['max_cards']
        
        while len(cards_data) < max_cards and no_new_cards < self.selectors['scroll_config']['no_new_cards_threshold']:
            # Encontrar cards atuais
            card_elements = await self.page.query_selector_all(self.selectors['maps']['result_cards'])
            
            for card in card_elements:
                try:
                    # Nome
                    name_elem = await card.query_selector(self.selectors['maps']['card_name'])
                    name = await name_elem.inner_text() if name_elem else ""
                    if not name or name in seen_names:
                        continue
                    seen_names.add(name)
                    
                    # Nota
                    rating_elem = await card.query_selector(self.selectors['maps']['card_rating'])
                    rating_text = await rating_elem.get_attribute('aria-label') if rating_elem else ""
                    rating_match = re.search(r'(\d[.,]\d)', rating_text)
                    nota = float(rating_match.group(1).replace(',', '.')) if rating_match else 0.0
                    
                    # Avaliações
                    reviews_elem = await card.query_selector(self.selectors['maps']['card_reviews'])
                    reviews_text = await reviews_elem.inner_text() if reviews_elem else ""
                    reviews_match = re.search(r'(\d[\d\.]*)', reviews_text.replace('.', ''))
                    avaliacoes = int(reviews_match.group(1).replace('.', '')) if reviews_match else 0
                    
                    # Tem site?
                    site_btn = await card.query_selector(self.selectors['maps']['card_website_button'])
                    tem_site = site_btn is not None
                    
                    # Telefone
                    phone_elem = await card.query_selector(self.selectors['maps']['card_phone_button'])
                    telefone = ""
                    if phone_elem:
                        telefone = await phone_elem.get_attribute('aria-label') or ""
                        telefone = telefone.replace('Telefone: ', '').strip()
                    
                    # Endereço
                    addr_elem = await card.query_selector(self.selectors['maps']['card_address'])
                    endereco = await addr_elem.inner_text() if addr_elem else ""
                    
                    cards_data.append({
                        'nome': name,
                        'nota': nota,
                        'avaliacoes': avaliacoes,
                        'tem_site': tem_site,
                        'telefone': telefone,
                        'endereco': endereco,
                        'card_element': card
                    })
                    
                except Exception as e:
                    continue
            
            # Scroll para carregar mais
            before_count = len(cards_data)
            await self.page.evaluate("window.scrollBy(0, 2000)")
            await self.page.wait_for_timeout(self.selectors['scroll_config']['scroll_pause_ms'])
            
            if len(cards_data) == before_count:
                no_new_cards += 1
            else:
                no_new_cards = 0
            
            print(f"   📍 {len(cards_data)} estabelecimentos carregados...")
        
        return cards_data

    async def get_place_details(self, card_element) -> Dict:
        """Clica no card e extrai detalhes completos"""
        try:
            await card_element.click()
            await self.page.wait_for_timeout(self.selectors['wait_times']['card_click'])
            
            detail = {}
            
            # Nome
            name_elem = await self.page.query_selector(self.selectors['place_detail']['name'])
            detail['nome'] = await name_elem.inner_text() if name_elem else ""
            
            # Nota
            rating_elem = await self.page.query_selector(self.selectors['place_detail']['rating'])
            rating_text = await rating_elem.get_attribute('aria-label') if rating_elem else ""
            rating_match = re.search(r'(\d[.,]\d)', rating_text)
            detail['nota'] = float(rating_match.group(1).replace(',', '.')) if rating_match else 0.0
            
            # Avaliações
            reviews_elem = await self.page.query_selector(self.selectors['place_detail']['reviews_count'])
            reviews_text = await reviews_elem.inner_text() if reviews_elem else ""
            reviews_match = re.search(r'(\d[\d\.]*)', reviews_text.replace('.', ''))
            detail['avaliacoes'] = int(reviews_match.group(1).replace('.', '')) if reviews_match else 0
            
            # Endereço
            addr_elem = await self.page.query_selector(self.selectors['place_detail']['address'])
            detail['endereco'] = await addr_elem.inner_text() if addr_elem else ""
            
            # Telefone
            phone_elem = await self.page.query_selector(self.selectors['place_detail']['phone'])
            if phone_elem:
                phone_text = await phone_elem.get_attribute('aria-label') or ""
                detail['telefone'] = phone_text.replace('Telefone: ', '').strip()
            
            # Site
            site_elem = await self.page.query_selector(self.selectors['place_detail']['website'])
            if site_elem:
                detail['site_atual'] = await site_elem.get_attribute('href') or ""
            else:
                site_btn = await self.page.query_selector(self.selectors['place_detail']['website_button'])
                if site_btn:
                    await site_btn.click()
                    await self.page.wait_for_timeout(self.selectors['wait_times']['site_load'])
                    detail['site_atual'] = self.page.url
                    await self.page.go_back()
                    await self.page.wait_for_timeout(1000)
            
            return detail
            
        except Exception as e:
            return {'erro': str(e)}

    async def process_lead(self, card_data: Dict, nicho: str, cidade: str) -> Optional[Lead]:
        """Processa um card: verifica filtros, analisa site, qualifica lead"""
        nome = card_data['nome']
        nota = card_data['nota']
        avaliacoes = card_data['avaliacoes']
        telefone = card_data['telefone']
        tem_site = card_data['tem_site']
        site_atual = card_data.get('site_atual', '')
        endereco = card_data.get('endereco', '')
        
        slug = slugify(f"{nome}-{cidade}")
        if slug in self.leads_existentes:
            return None
        
        # Filtro 1: Potencial financeiro
        nota_min = self.prospeccao_config.get('notaMinima', 4.7)
        aval_min = self.prospeccao_config.get('avaliacoesMinimas', 40)
        
        if nota < nota_min or avaliacoes < aval_min:
            return Lead(
                slug=slug, nome=nome, nota=nota, avaliacoes=avaliacoes,
                telefone=telefone, cidade=cidade, nicho=nicho,
                motivo=f"Filtro potencial: nota {nota} < {nota_min} ou avaliações {avaliacoes} < {aval_min}",
                status="descartado"
            )
        
        # Filtro 2: Tem site ativo
        if not tem_site or not site_atual:
            return Lead(
                slug=slug, nome=nome, nota=nota, avaliacoes=avaliacoes,
                telefone=telefone, cidade=cidade, nicho=nicho,
                motivo="Sem site ativo ou site inacessível",
                status="descartado"
            )
        
        # Verificar se é diretório terceiro
        if is_third_party_directory(site_atual):
            return Lead(
                slug=slug, nome=nome, nota=nota, avaliacoes=avaliacoes,
                telefone=telefone, cidade=cidade, nicho=nicho,
                site_atual=site_atual,
                motivo="Site aponta para diretório de terceiros",
                status="descartado"
            )
        
        # Filtro 3: Site ruim - analisar qualidade
        quality = await analyze_website_quality(self.page, site_atual)
        
        if not quality['ruim']:
            return Lead(
                slug=slug, nome=nome, nota=nota, avaliacoes=avaliacoes,
                telefone=telefone, cidade=cidade, nicho=nicho,
                site_atual=site_atual,
                motivo="Site com qualidade aceitável",
                status="descartado"
            )
        
        # Filtro 4: E-mail obrigatório
        email = ""
        if quality['emails']:
            email = quality['emails'][0]
        else:
            # Buscar no Google
            email = await self.search_email_google(nome, cidade)
        
        if not email:
            return Lead(
                slug=slug, nome=nome, nota=nota, avaliacoes=avaliacoes,
                telefone=telefone, whatsapp=quality['whatsapp'],
                cidade=cidade, nicho=nicho, site_atual=site_atual,
                motivo="; ".join(quality['motivos']),
                status="descartado"
            )
        
        # LEAD QUALIFICADO!
        whatsapp = quality['whatsapp']
        if not whatsapp and telefone:
            tel_digits = re.sub(r'\D', '', telefone)
            if len(tel_digits) >= 10 and tel_digits[-9] == '9':
                whatsapp = normalize_phone(telefone)
        
        return Lead(
            slug=slug,
            nome=nome,
            nota=nota,
            avaliacoes=avaliacoes,
            telefone=telefone,
            whatsapp=whatsapp,
            email=email,
            site_atual=site_atual,
            motivo="; ".join(quality['motivos']),
            cidade=cidade,
            nicho=nicho,
            endereco=endereco,
            status="novo"
        )

    async def search_email_google(self, nome: str, cidade: str) -> str:
        """Busca e-mail no Google (fallback)"""
        try:
            query = f"{nome} {cidade} email contato"
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            await self.page.goto(url, wait_until='networkidle')
            await self.page.wait_for_timeout(2000)
            content = await self.page.content()
            emails = extract_emails(content)
            for e in emails:
                if not any(g in e.lower() for g in ['@gmail.', '@hotmail.', '@yahoo.', '@outlook.', 'noreply', 'no-reply']):
                    return e
            return emails[0] if emails else ""
        except:
            return ""

    async def run_prospeccao(self, nicho: str, cidade: str, meta_leads: int = 10) -> List[Lead]:
        """Executa prospecção completa"""
        print(f"\n🔍 Iniciando prospecção: {nicho} em {cidade} (meta: {meta_leads} leads)")
        
        await self.init_browser()
        leads_qualificados = []
        leads_descartados = []
        total_avaliados = 0

        try:
            # 1. Buscar cards no Maps
            cards = await self.search_maps(nicho, cidade)
            print(f"📍 {len(cards)} estabelecimentos encontrados no Maps")

            # 2. Processar cada card
            for i, card_data in enumerate(cards):
                if len(leads_qualificados) >= meta_leads:
                    break
                if total_avaliados >= 25:
                    break

                total_avaliados += 1
                print(f"\n[{total_avaliados}/25] Analisando: {card_data['nome']} (⭐{card_data['nota']} | {card_data['avaliacoes']} aval.)")

                # Pegar detalhes completos
                detail = await self.get_place_details(card_data['card_element'])
                if detail.get('erro'):
                    continue
                
                card_data.update(detail)

                # Processar lead
                lead = await self.process_lead(card_data, nicho, cidade)
                
                if lead:
                    if lead.status == "novo":
                        leads_qualificados.append(lead)
                        print(f"   ✅ LEAD QUALIFICADO! ({len(leads_qualificados)}/{meta_leads})")
                        print(f"   📧 {lead.email} | 📱 {lead.whatsapp or lead.telefone}")
                        print(f"   🎯 Motivo: {lead.motivo}")
                    else:
                        leads_descartados.append(lead)
                        print(f"   ❌ Descartado: {lead.motivo}")

                # Rate limiting
                delay = self.playwright_config.get('delay_entre_requisicoes_ms', 2000)
                await asyncio.sleep(delay / 1000)

            print(f"\n✅ Prospecção concluída!")
            print(f"   Qualificados: {len(leads_qualificados)}")
            print(f"   Descartados: {len(leads_descartados)}")
            print(f"   Total avaliados: {total_avaliados}")

            return leads_qualificados + leads_descartados

        finally:
            await self.save_state()
            await self.close()


# ============================================================
# EXPORTAÇÃO DE RESULTADOS
# ============================================================

def save_leads_md(leads: List[Lead], nicho: str, cidade: str):
    """Atualiza leads.md local (append + update, não sobrescreve status avançado)"""
    existing = {}
    if LEADS_FILE.exists():
        content = LEADS_FILE.read_text()
        for line in content.split('\n'):
            if '|' in line and not line.startswith('| #') and not line.startswith('|---'):
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 10 and parts[1] not in ['Nome', '---']:
                    slug = slugify(parts[1])
                    existing[slug] = line

    # Header
    lines = [
        "| # | Nome | Nota | Aval. | E-mail | Telefone | WhatsApp | Site atual | Motivo | Status | URL nova |",
        "|---|------|------|-------|--------|----------|----------|------------|--------|--------|----------|"
    ]

    status_ordem = {'novo': 0, 'redesenhado': 1, 'publicado': 2, 'proposta enviada': 3, 'descartado': 4}
    
    all_leads = {l.slug: l for l in leads}
    for slug, line in existing.items():
        if slug in all_leads:
            new_lead = all_leads[slug]
            if status_ordem.get(new_lead.status, 0) > status_ordem.get('novo', 0):
                pass
            else:
                continue
        lines.append(line)

    # Adicionar/atualizar leads novos
    for i, lead in enumerate(leads, 1):
        linha = f"| {i} | {lead.nome} | {lead.nota} | {lead.avaliacoes} | {lead.email} | {lead.telefone} | {lead.whatsapp} | {lead.site_atual} | {lead.motivo} | {lead.status} | {lead.url_nova} |"
        lines.append(linha)

    LEADS_FILE.write_text('\n'.join(lines))
    print(f"📝 leads.md atualizado: {LEADS_FILE}")


async def save_google_sheets(leads: List[Lead], nicho: str, cidade: str) -> str:
    """Salva no Google Sheets via API - placeholder por enquanto"""
    return f"https://docs.google.com/spreadsheets/d/PLACEHOLDER_{nicho}_{cidade}"


# ============================================================
# CLI / ENTRY POINT
# ============================================================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description='Prospector Playwright - Google Maps Scraper')
    parser.add_argument('nicho', nargs='?', help='Nicho para prospecção (ex: nutricionistas)')
    parser.add_argument('cidade', nargs='?', help='Cidade (ex: São Paulo)')
    parser.add_argument('--meta', type=int, default=10, help='Meta de leads qualificados')
    parser.add_argument('--config', help='Caminho do config JSON')
    args = parser.parse_args()

    config = load_config()
    if args.config:
        config.update(json.loads(Path(args.config).read_text()))

    nicho = args.nicho or config.get('prospeccao', {}).get('nichos', ['nutricionistas'])[0]
    cidade = args.cidade or config.get('prospeccao', {}).get('cidade', 'São Paulo')
    meta = args.meta or config.get('prospeccao', {}).get('leadsPorBusca', 10)

    scraper = MapsScraper(config)
    leads = await scraper.run_prospeccao(nicho, cidade, meta)

    # Salvar resultados
    save_leads_md(leads, nicho, cidade)
    sheets_url = await save_google_sheets(leads, nicho, cidade)

    # Output para o menu/dashboard
    result = {
        'nicho': nicho,
        'cidade': cidade,
        'total_qualificados': len([l for l in leads if l.status == 'novo']),
        'total_descartados': len([l for l in leads if l.status == 'descartado']),
        'leads': [asdict(l) for l in leads],
        'sheets_url': sheets_url,
        'timestamp': datetime.now().isoformat()
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
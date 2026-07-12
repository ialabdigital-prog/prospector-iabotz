---
name: redesign-premium
description: Esta skill deve ser usada ao redesenhar páginas de leads qualificados — recriar com estética premium, conteúdo real aprimorado, fotos e logo originais, seções novas relevantes, gerando editor visual e comparador antes/depois. Acione quando o usuário disser "redesenhar", "refazer o site", "criar página" ou rodar /redesenhar.
---

# Redesign Premium

Recriar a página do lead com estética premium: conteúdo real aprimorado, fotos e logo originais, seções novas relevantes. Gerar junto o editor visual e o comparador antes/depois.

## Entrada

- Lead qualificado (status `novo` em `leads.md` / dashboard)
- URL do site atual (`site_atual`)
- Dados do lead: nome, nicho, cidade, telefone, WhatsApp, e-mail, endereço

## Extração de Conteúdo (do site atual)

Acesse o site atual e extraia **tudo que for aproveitável**:

- **Textos**: sobre, serviços, diferenciais, depoimentos, equipe, FAQ, localização
- **Imagens**: logo, fotos do local/equipe/produtos, banner hero
- **Cores**: paleta da marca (extrair do CSS ou logo)
- **Estrutura**: menus, CTAs, formulários, integrações (WhatsApp, agendamento)
- **SEO**: meta title/description, headings, schema.org se houver

**Regra**: não invente — aprimore o que existe. Se faltar conteúdo, use placeholders genéricos do nicho (ex.: "Atendimento humanizado e personalizado") e marque para o cliente revisar no editor.

## Geração da Nova Página (`sites/[slug]/index.html`)

### Estrutura Obrigatória (Mobile-First)

1. **Hero** (above the fold)
   - Headline clara com benefício principal + nicho + cidade
   - Subheadline de apoio (1 linha)
   - **CTA principal**: botão WhatsApp (`wa.me/55...`) + botão secundário "Agendar" (link para seção contato ou Calendly)
   - Imagem de fundo ou ilustração relevante (otimizada WebP, lazy-load)

2. **Sobre / Autoridade**
   - Texto "Sobre nós" reescrito com tom profissional
   - Credenciais: formação, experiência, certificações, associações
   - **Prova social**: carrossel de depoimentos (se houver no site atual) + nota do Google Maps + nº de avaliações

3. **Serviços** (cards)
   - Cada serviço: ícone/imagem, título, descrição curta, benefício
   - CTA por card: "Saiba mais" → abre modal ou scroll para contato

4. **Diferenciais / Por que escolher** (3-4 ícones + texto)

5. **Equipe** (se aplicável)
   - Cards com foto, nome, especialidade, mini-bio

6. **Depoimentos** (carrossel)
   - Nome, foto (se houver), texto, nota ⭐⭐⭐⭐⭐
   - Link "Ver todas no Google Maps" → abre perfil do Maps

7. **FAQ** (schema.org FAQPage)
   - 5-8 perguntas frequentes do nicho

8. **Contato / Localização**
   - Mapa incorporado (Google Maps embed)
   - Endereço completo, telefone, WhatsApp, e-mail
   - Formulario simples (Nome, WhatsApp, Mensagem) → webhook/email
   - Horário de funcionamento

9. **Footer**
   - Logo, links rápidos, redes sociais, copyright, LGPD/privacidade

### Requisitos Técnicos

- **HTML semântico** + **CSS custom properties** (variáveis para cores, fontes, espaçamento)
- **Mobile-first**: breakpoints 480px, 768px, 1024px, 1280px
- **Performance**: CSS crítico inline, JS mínimo (só menu mobile, carrossel, smooth scroll), imagens WebP com `srcset` + `loading=lazy`
- **SEO on-page**: meta tags, Open Graph, Twitter Card, JSON-LD (LocalBusiness, ProfessionalService)
- **Acessibilidade**: contraste AA, alt texts, focus visible, landmarks ARIA
- **CTAs WhatsApp** em posições estratégicas: hero, após serviços, footer, sticky bottom mobile

## Editor Visual (`sites/[slug]/editor.html`)

Página standalone que carrega o `index.html` em `<iframe>` + toolbar lateral:

- **Modo edição**: clique em qualquer texto → `contentEditable` → toolbar flutuante (negrito, itálico, link, heading, cor)
- **Imagens**: clique → modal para upload (base64 local) ou URL → substitui `src`
- **Cores/tipografia**: painel com variáveis CSS (`--color-primary`, `--font-heading`, `--spacing-unit`) → alteração em tempo real no iframe
- **Seções**: drag-and-drop para reordenar, add/remove (snippets pré-definidos)
- **Preview**: toggle mobile (375px) / desktop (1440px)
- **Exportar**: botão "Salvar HTML final" → baixa `index.html` com todas as edições aplicadas (resolve `contentEditable` → HTML limpo)

## Comparador Antes/Depois (`sites/[slug]/comparador.html`)

- **Slider lateral** (range input): esquerda = screenshot do site atual (Puppeteer/Playwright, 1440x900 + 375x667), direita = nova página (iframe vivo ou screenshot)
- **Tabs**: Desktop | Mobile
- **Overlay**: marcadores visuais nos pontos de melhoria (CTA, hero, prova social, etc.)
- **Botão**: "Abrir editor" → linka para `editor.html`

## Atualização de Status

Ao concluir:
- `leads.md`: status → `redesenhado`
- Dashboard SQLite: `UPDATE leads SET status='redesenhado' WHERE slug=...`
- Regenerar `dashboard.html` snapshot

## Boas Práticas

- **Não prometa o que não tem**: se o site atual não tem fotos, use placeholders profissionais (Unsplash/Pexels via busca por nicho) e avise no editor
- **Mantenha a identidade**: cores/logo do cliente — não imponha seu gosto
- **Copywriting**: reescreva para clareza e conversão (headlines com benefício, bullets escaneáveis, verbos de ação)
- **Teste real**: abra o `index.html` no mobile real antes de considerar pronto
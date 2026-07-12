---
description: Redesenha as páginas dos leads qualificados com estética premium, gera editor visual e comparador antes/depois
argument-hint: "[nome do cliente ou todos]"
---

Redesenhe páginas seguindo a skill `redesign-premium`.

## Passos

1. Determine o que redesenhar: `$ARGUMENTS` (um cliente ou "todos"), ou liste os leads com status `novo` em `leads.md` e pergunte.
2. Para cada lead:
   - Leia o site atual (`site_atual` no lead)
   - Extraia conteúdo real: textos, imagens, logo, cores, estrutura, serviços, depoimentos, equipe, localização
   - **Gere a nova página** (`sites/[slug]/index.html`) com:
     - Hero com proposta de valor clara + CTA WhatsApp/agenda acima da dobra
     - Seções: Sobre, Serviços (cards), Depoimentos (carrossel se houver), Equipe, Localização/Contato, FAQ
     - Design premium: tipografia moderna, espaçamento generoso, cores da marca, imagens otimizadas
     - Totalmente responsivo (mobile-first)
     - SEO on-page: meta tags, schema.org, heading hierarchy
     - Performance: CSS/JS inline crítico, lazy loading, WebP
   - **Gere o editor visual** (`sites/[slug]/editor.html`): página que carrega o `index.html` em iframe + toolbar lateral para editar textos/imagens/clicar e digitar, com botão "Exportar HTML final"
   - **Gere o comparador antes/depois** (`sites/[slug]/comparador.html`): slider lateral (antes | depois) + screenshots mobile/desktop
3. Atualize `leads.md` e dashboard: status `redesenhado`.

## Saída

Liste, por cliente: pasta do site (`sites/[slug]/`), arquivos gerados (`index.html`, `editor.html`, `comparador.html`). Sugira o próximo passo: `/editor` para ajustes finos ou `/publicar` para colocar no ar.
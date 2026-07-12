---
name: prospeccao-playwright
description: Esta skill deve ser usada ao prospectar clientes no Google Maps usando Playwright (headless) — buscar negócios bem avaliados (nota ≥ 4.7, avaliações ≥ 40) com site ativo porém ruim e e-mail público. Roda no servidor, não depende do Chrome do usuário. Acione quando o usuário disser "prospectar", "buscar clientes", "achar leads", "clientes com site ruim" ou rodar /prospectar.
---

# Prospecção no Google Maps via Playwright

Encontrar o cliente ouro: negócio que JÁ fatura bem (nota alta, muitas avaliações) mas perde clientes por causa de um site fraco. Não se cria demanda — conserta-se onde o dinheiro está escapando.

## Arquitetura

- **Roda no servidor** (mesmo servidor do aapanel) via Playwright headless
- **Não precisa do Chrome do usuário** — execução 100% server-side
- **Persiste sessão** (cookies, localStorage) para evitar CAPTCHA/login repetido
- **Rate limiting** e user-agent rotation para evitar bloqueio

## Configuração (prospector-config.json → bloco `playwright`)

```json
"playwright": {
  "headless": true,
  "browser": "chromium",
  "timeout_ms": 30000,
  "delay_entre_requisicoes_ms": 2000,
  "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...",
  "viewport": { "width": 1366, "height": 768 },
  "proxy": "",
  "stealth": true
}
```

## Fluxo de Execução

1. **Inicializar Playwright** com config acima (stealth mode se habilitado)
2. **Carregar estado persistente** (`playwright-state.json`) se existir — mantém login/cookies do Google
3. **Buscar** `https://www.google.com/maps/search/[nicho]+em+[cidade]`
4. **Scroll infinito** + extração de cards (nome, nota, nº avaliações, site, telefone, endereço)
5. **Para cada candidato** (até max 25 estabelecimentos ou meta de leads):
   - **Filtro 1 — Potencial**: nota ≥ `notaMinima` (padrão 4.7) E avaliações ≥ `avaliacoesMinimas` (padrão 40)
   - **Filtro 2 — Tem site ativo**: abre site em nova aba, verifica HTTP 200, não é diretório terceiros
   - **Filtro 3 — Site ruim**: analisa qualidade (critérios abaixo). Site bom → descarta. Site ruim → candidato
   - **Filtro 4 — E-mail obrigatório**: extrai e-mail do site (rodapé, contato, mailto:, busca Google). Sem e-mail → descarta
6. **Parar** ao atingir meta de leads qualificados (`leadsPorBusca`, padrão 10) ou 25 estabelecimentos avaliados
7. **Pular** estabelecimentos já em `leads.md` (slug = nome normalizado + cidade)

## Critérios de Site Ruim (registrar motivo específico)

Qualifica como lead se o site (ativo) tiver **2 ou mais** destes problemas:

- **Layout datado** (template 10+ anos, fontes de sistema, imagens esticadas/pixeladas)
- **Sem CTA claro** de agendamento/contato (nenhum botão WhatsApp/agenda visível above-the-fold)
- **Domínio gratuito/plataforma alheia** (Google Sites, Wix grátis, subdomínio com marca da plataforma)
- **Não responsivo** (quebra no mobile — testar viewport 375px)
- **Conteúdo desorganizado**: serviços escondidos, sem hierarquia, texto corrido sem seções
- **Sem prova social** (nenhuma avaliação/depoimento no site, apesar de nota alta no Maps)

**Motivo anotado deve ser objetivo e verificável** — será citado na proposta.
Ex.: `"domínio redireciona para Google Sites gratuito, template básico, sem CTA de agendamento"`

## Coleta por Lead

| Campo | Fonte | Observação |
|-------|-------|------------|
| `nome` | Maps card | Nome exato do estabelecimento |
| `nota` | Maps card | Float (ex: 4.8) |
| `avaliacoes` | Maps card | Int (ex: 127) |
| `telefone` | Maps card / site | Formato bruto |
| `whatsapp` | Site (wa.me/, api.whatsapp.com) OU telefone com 9º dígito (celular BR) | **SEMPRE capturar**, formato internacional `55 + DDD + número` (ex: `5511999990000`) |
| `email` | Site (rodapé, contato, mailto:) OU busca Google `[nome] + email/contato` | **OBRIGATÓRIO** — sem e-mail = descarte |
| `site_atual` | Maps card / site | URL completa |
| `motivo` | Análise automática | String descritiva dos 2+ problemas |
| `cidade` | Config / Maps | |
| `nicho` | Config | |
| `slug` | Gerado | `nome-cidade` normalizado (kebab-case, sem acentos) |
| `endereco` | Maps card | Opcional |

## WHATSAPP — Regra de Ouro

**Capture SEMPRE, separado do telefone.**
Fontes (ordem de prioridade):
1. Link/botão WhatsApp no site do lead (`wa.me/`, `api.whatsapp.com`, ícone WhatsApp) — extrair número do link
2. Telefone celular do perfil do Maps (números com 9º dígito = celular no Brasil — assuma WhatsApp)
3. Se só tem fixo, tentar WhatsApp Business via `wa.me/55DDDnumero`

Registre no formato internacional `55 + DDD + número` (ex: `5511999990000`), pronto pra `wa.me`.
O WhatsApp alimenta botões do dashboard e plano B de abordagem quando e-mail não responde.

## Saída — Google Sheets + leads.md local + Dashboard (SQLite)

### 1. Google Sheets (principal)
Via conector Google Drive: `create_file` com CSV em `textContent` + `contentMimeType: text/csv` → converte para Sheets nativo.
Título: `Leads Prospector — [nicho] [cidade] [data]`
Colunas: `# | Nome | Nota | Aval. | E-mail | Telefone | WhatsApp | Site atual | Motivo | Situação | Status | URL nova`
Incluir **TODOS** avaliados (qualificados E descartados), ranqueados por potencial (melhor nota + pior site primeiro).
Retornar **link da planilha** ao usuário.

### 2. Cópia local `leads.md` (mesmas colunas)
Controle de status — o conector Drive não edita células.
Status possíveis: `novo`, `redesenhado`, `publicado`, `proposta enviada`, `descartado`.
Quando status mudar (redesenhar/publicar/proposta), regenerar planilha Google com dados acumulados + atualizar `dashboard.html` (skill `dashboard-leads`).
**Nunca sobrescrever leads antigos** — apenas acrescentar e atualizar.

### 3. Dashboard SQLite (`prospector.db`) — skill `dashboard-leads`
Upsert na tabela `leads` (ver schema na skill `dashboard-leads`).
Regenerar snapshot JSON no `dashboard.html`.

## Boas Práticas

- **Trabalhar por região** dá vantagem: menos concorrência na oferta e conhecimento local
- **Não interromper** o fluxo com perguntas — só reportar a tabela final
- **Se Google Maps pedir login/captcha**: pausar, salvar estado (`playwright-state.json`), avisar usuário para resolver manualmente uma vez
- **Rate limiting**: delay configurável entre requisições (padrão 2s)
- **Proxy opcional**: se configurado, usar para rotação de IP
- **Stealth mode**: `playwright-stealth` para evitar detecção de bot

## Tratamento de Erros

| Erro | Ação |
|------|------|
| Timeout navegação | Retry 1x, depois pular estabelecimento |
| CAPTCHA detectado | Salvar estado, avisar usuário, aguardar intervenção |
| Site fora do ar (não 200) | Registrar como "site inacessível" → descartar (Filtro 2) |
| Site é diretório terceiros | Registrar como "diretório terceiro" → descartar (Filtro 2) |
| Sem e-mail após busca | Registrar como "sem e-mail público" → descartar (Filtro 4) |
| Playwright crash | Reiniciar browser, continuar do último processado |
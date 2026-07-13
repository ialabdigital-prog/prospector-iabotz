# 🚀 Prospector IA Botz

**Descubra. Redesigne. Publique. Converta.**

> ⚠️ **Projeto 100% em desenvolvimento** — toda contribuição, ideia, issue e pull request é super bem-vinda!  
> 🌐 Conheça nosso ecossistema de agentes de IA em [iabotz.com.br](https://iabotz.com.br)  
> 💡 **Gratuito** — código aberto, sem taxas, sem licenças pagas. A ideia é compartilhar o que viemos construindo.

---

## 🎯 O que é o Prospector IA Botz?

Uma plataforma **completa e gratuita** de prospecção comercial que **descobre leads**, **analisa a presença digital**, **redesenha sites com IA**, **publica em subdomínios seguros** e **prepara propostas comerciais** via e-mail e WhatsApp — tudo em um único painel web.

O sistema foi inspirado no projeto público [PROSPECTOR-DE-SITES](https://github.com/ArrecheNeto/PROSPECTOR-DE-SITES), mas substitui o dashboard estático e comandos CLI originais por uma **aplicação Flask completa**, com API autenticada, fila persistente, worker dedicado, Kanban, follow-ups e integrações nativas.

> ⚠️ **Projeto 100% em desenvolvimento** — toda contribuição, issue, ideia e pull request é super bem-vinda!  
> 🌐 Conheça nosso ecossistema de agentes de IA em [iabotz.com.br](https://iabotz.com.br)  
> 💰 **100% gratuito** — código aberto (MIT), sem taxas, sem licenças pagas. A ideia é compartilhar o que viemos construindo.

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Fluxo Completo](#-fluxo-completo)
- [Funcionalidades](#-funcionalidades)
- [Arquitetura](#-arquitetura)
- [Provedores Suportados](#-provedores-suportados)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [CLI](#-cli)
- [Segurança](#-segurança)
- [Roadmap](#-roadmap)
- [Contribuição](#-contribuição)
- [Licença](#-licença)

---

## 🚀 Visão Geral

**Prospector IA Botz** é uma plataforma open-source de prospecção comercial que automatiza todo o ciclo de **descoberta → qualificação → redesign → publicação → outreach** para negócios locais com presença digital fraca.

O sistema busca leads no **Google Maps** por nicho e localidade, analisa a qualidade do site, e se for ruim, **redesenha automaticamente com IA** — gerando sites visualmente únicos, com imagens originais via KIE, e prepara propostas comerciais via **e-mail (Gmail)** e **WhatsApp (Evolution API/Go)**.

Tudo gerenciado por um **painel web premium** com Kanban, follow-ups inteligentes e integração com múltiplos provedores de IA.

---

## ✨ Funcionalidades

### 🔍 Descoberta Inteligente de Leads
- Busca em **Google Maps** por nicho e cidade
- Complemento automático com **Apify** quando resultados são insuficientes
- Deduplicação inteligente de candidatos
- Limites configuráveis por prospecção

### ✅ Qualificação Automática
- Verifica pontuação TC (mínimo configurável)
- Detecta sites inexistentes, fora do ar ou de baixa qualidade
- Negócios fortes com site inválido + contato útil = **oportunidade de reconstrução**
- Classifica sites maduros para estratégia `source-led`

### 🎨 Redesign com IA (LLM + KIE)
- **32 direções visuais** com múltiplas composições por estilo
- Briefing criativo selecionado por **nicho, histórico e LLM**
- **Extração de identidade visual** do site original: logo, paleta CSS, imagens públicas
- **Variação por marca**: composição, hero, superfície, densidade, ritmo, ênfase
- **Estratégia source-led**: preserva navegação, conteúdo, artigos, FAQ de sites maduros
- **Quality gate**: bloqueia versões que perdem serviços, artigos, FAQ, logo ou falham no QA
- **Geração de imagens via KIE MCP**: hero 16:9, suporte 4:5, detalhe 1:1
- **Efeitos SVG animados**, CTA de WhatsApp flutuante
- **Capturas de tela** com Playwright (desktop + mobile)

### 🤖 Múltiplos Provedores de IA
Conecte-se com **qualquer LLM** que preferir:

| Provedor | Tipo |
|---|---|
| **OpenRouter** | API key (recomendado) |
| **Claude (Anthropic)** | API key |
| **OpenAI (GPT-4, etc.)** | API key |
| **Gemini (Google)** | API key |
| **Codex (Amazon)** | CLI |
| **Ollama** | Local (open-source) |
| **Qualquer OpenAI-compatível** | API key |

### 🖼️ Geração de Imagens com KIE MCP
Cada redesign gera **imagens originais e únicas** via KIE (Kling Image Engine):
- Hero 16:9 — banner principal
- Suporte 4:5 — imagem secundária
- Detalhe 1:1 — imagem de destaque
- Manifesto completo: prompt, modelo, task ID, path, proporção
- Novas imagens a cada regeneração visual

### 📧 Propostas Comerciais
- **E-mail**: integração com **Gmail via Composio** para evitar spam
- **WhatsApp**: via **Evolution API** ou **Evolution Go**
- Página de proposta com **print do antes e depois** do redesign
- Modo rascunho seguro: nada é enviado sem autorização explícita
- Trava de segurança: só envia se `proposta.html`, screenshots e HTTPS público estiverem OK

### 📊 Kanban & Pipeline
- **7 estágios**: Novo → Redesenhado → Publicado → Proposta → Respondeu → Fechado → Descartado
- **Drag-and-drop** no desktop, seletor de estágio no mobile
- Badge indicando outreach preparado mas não enviado
- Alerta de follow-up pendente
- Campo de valor opcional para leads fechados

### 🔄 Follow-up Inteligente
- Elegibilidade após **3 dias úteis** sem resposta
- Verificação de respostas no Gmail antes de follow-up
- Máximo **1 follow-up por canal**
- E-mail cria draft no Gmail + cópia no painel
- WhatsApp cria draft ou envia via Evolution
- Execução individual ou em lote
- Rotina diária opcional em Config > Canais

### 🚀 Deploy Automático
- **aaPanel** para hospedagem
- **Cloudflare** para DNS automático com subdomínios
- Certificado HTTPS automático
- Hostname público derivado do domínio do lead
- Validação de DNS e HTTPS antes de liberar

### 📸 Screenshots com Playwright
- Captura desktop (1440px) e mobile (375px)
- Usado na página de proposta (antes/depois)
- **Planejamos substituir o Playwright** por uma solução mais leve no futuro

---

## 🔧 Provedores Suportados

### 🤖 LLM (Geração de Conteúdo e Variação Visual)
| Provedor | Tipo | Status |
|---|---|---|
| **OpenRouter** | API key | ✅ Recomendado |
| **Claude (Anthropic)** | API key | ✅ |
| **OpenAI (GPT-4, GPT-4o, etc.)** | API key | ✅ |
| **Gemini (Google)** | API key | ✅ |
| **Codex (Amazon)** | CLI | ✅ |
| **Ollama** | Local (open-source) | ✅ |
| **Qualquer OpenAI-compatível** | API key | ✅ |

### 🖼️ Geração de Imagens
| Provedor | Tipo | Status |
|---|---|---|
| **KIE MCP** (Kling Image Engine) | API | ✅ |

### 📧 Outreach
| Canal | Integração | Status |
|---|---|---|
| **E-mail** | Gmail via Composio | ✅ |
| **WhatsApp** | Evolution API / Evolution Go | ✅ |

### 🚀 Deploy
| Serviço | Função | Status |
|---|---|---|
| **aaPanel** | Hospedagem e gerenciamento | ✅ |
| **Cloudflare** | DNS automático + subdomínios | ✅ |
| **Let's Encrypt** | Certificado HTTPS | ✅ |

---

## 🧠 Como Funciona (Fluxo Completo)

```
Google Maps ──> Descoberta ──> Qualificação ──> Direção Criativa ──> Redesign com IA
       │                                                            │
       └── Apify (complemento)                                      ├── KIE gera imagens
                                                                    ├── LLM gera variação
                                                                    ├── Render HTML + SVG
                                                                    └── Playwright screenshots
                                                                           │
                                                                           ▼
                                                              ┌── Publicação (aaPanel + Cloudflare)
                                                              │   ├── DNS automático
                                                              │   ├── HTTPS automático
                                                              │   └── Subdomínio público
                                                              │
                                                              └── Outreach
                                                                  ├── E-mail (Gmail — sem spam)
                                                                  ├── WhatsApp (Evolution API/Go)
                                                                  └── Página de proposta (antes/depois)
                                                                         │
                                                                         ▼
                                                              ┌── Kanban (Pipeline)
                                                              ├── Follow-up (3 dias úteis)
                                                              └── Resposta → Fechado
```

---

## ✨ Funcionalidades em Detalhe

### 🔍 Descoberta de Leads
- Busca em **Google Maps** por nicho + cidade
- Complemento automático com **Apify** se resultados insuficientes
- Deduplicação inteligente
- Limites configuráveis por prospecção

### ✅ Qualificação
- Verifica **pontuação TC** mínima
- Detecta **sites inexistentes, fora do ar ou de baixa qualidade**
- Negócios fortes com site inválido + contato útil = **oportunidade de reconstrução**
- Classifica sites maduros para estratégia **source-led**

### 🎨 Redesign Premium com IA
- **Catálogo com 32 estilos visuais** e múltiplas composições por estilo
- **Briefing criativo** selecionado por nicho, histórico e LLM
- **Extração de identidade visual** do site original: logo, paleta CSS, imagens públicas
- **Variação por marca**: composição, hero, superfície, densidade, ritmo, ênfase
- **Source-led**: preserva navegação, conteúdo, artigos, FAQ de sites maduros
- **Quality gate**: bloqueia versões que perdem >30% serviços, >30% artigos, >50% FAQ
- **Geração de imagens via KIE MCP**: hero 16:9, suporte 4:5, detalhe 1:1
- **Efeitos SVG animados**, CTA de WhatsApp flutuante
- **Responsivo**: desktop e mobile

### 📧 Propostas
- **E-mail**: integração com **Gmail via Composio** — evita spam, cria drafts reais
- **WhatsApp**: via **Evolution API** ou **Evolution Go**
- **Página de proposta** com print do antes/depois
- **Modo rascunho**: nada é enviado sem autorização explícita
- **Trava de segurança**: valida proposta.html, screenshots, HTTPS público e imagens

### 📊 Kanban (Pipeline)
| Estágio | Descrição |
|---|---|
| 🆕 Novo | Lead descoberto e qualificado |
| 🎨 Redesenhado | Site gerado com IA |
| 🌐 Publicado | Site no ar com HTTPS |
| 📧 Proposta | Outreach enviado |
| 💬 Respondeu | Lead respondeu |
| ✅ Fechado | Negócio fechado (com valor opcional) |
| ❌ Descartado | Desqualificado |

### 🔄 Follow-up Inteligente
- **3 dias úteis** após envio sem resposta
- Verifica respostas no Gmail antes de follow-up
- Máximo **1 follow-up por canal**
- E-mail: cria draft no Gmail + cópia no painel
- WhatsApp: draft ou envio via Evolution
- Execução individual ou em lote
- Rotina diária automática opcional

### 🖥️ Painel Web Premium
- **Dashboard** com métricas ao vivo
- **Kanban** drag-and-drop
- **Jobs** assíncronos com status em tempo real
- **Configurações** de canais, provedores e rotinas
- **Histórico** de outreach completo
- Design premium com branding IA Botz

---

## 🏗️ Arquitetura

```
prospector-iabotz/
├── app/
│   ├── api/              APIs REST do painel
│   ├── discovery/        Busca (Google Maps, Apify) e qualificação
│   ├── jobs/             Fila e runners assíncronos
│   ├── llm/              Roteador multi-provedor
│   ├── static/           CSS, JS, imagens
│   └── templates/        HTML do painel
├── skills/
│   ├── deploy-aapanel/   DNS Cloudflare, upload, HTTPS
│   ├── proposta-email/   Geração de e-mail e follow-up
│   ├── proposta-whatsapp/ Drafts e Evolution API
│   └── redesign-premium/ Catálogo, assets, render, screenshots
├── scripts/              Importadores e deploy
├── worker.py             Consumidor da fila (lock exclusivo)
├── wsgi.py               Entrada do servidor web
└── prospector            CLI principal
```

---

## ⚡ Instalação Rápida

```bash
git clone https://github.com/ialabdigital-prog/prospector-iabotz.git
cd prospector-iabotz
./install.sh
cp prospector-config.example.json prospector-config.json
```

Configure as credenciais no arquivo local `prospector-config.json` (nunca versionado).

Crie o primeiro administrador:

```bash
export PROSPECTOR_ADMIN_USER='admin'
export PROSPECTOR_ADMIN_PASS='use-uma-senha-forte'
export PROSPECTOR_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Inicie o painel e o worker:

```bash
./venv/bin/gunicorn -b 127.0.0.1:8765 -w 2 --timeout 120 wsgi:app
./venv/bin/python worker.py
```

Acesse: `http://127.0.0.1:8765`

---

## 🔐 Segurança

- **Modo rascunho padrão**: nada é enviado sem autorização explícita
- **Trava de outreach**: valida proposta.html, screenshots, HTTPS público e imagens antes de enviar
- **Secrets ignorados pelo Git**: prospector-config.json, *.db, sites/, drafts/, logs/
- **Primeiro admin** exige credenciais explícitas de ambiente
- **Tokens com escopo mínimo** para Cloudflare, aaPanel, Google, Apify, KIE, LLM
- **Scanner de segredos** recomendado antes de commits

---

## 🤝 Contribuição

**Toda contribuição é super bem-vinda!** O projeto está 100% em desenvolvimento e queremos construir junto com a comunidade.

### Como contribuir

1. Faça um **fork** do repositório
2. Crie uma branch: `git checkout -b minha-feature`
3. Faça suas alterações (mantenha pequenas e testáveis)
4. Execute as verificações: `./venv/bin/python -m compileall -q app skills worker.py wsgi.py`
5. Commit e push: `git push origin minha-feature`
6. Abra um **Pull Request** descrevendo o que foi feito

### Ideias para contribuir
- Novos provedores de descoberta (Bing, Yelp, etc.)
- Novos estilos de redesign
- Mais integrações de outreach (Telegram, SMS)
- Melhorias no painel web
- Testes automatizados
- Documentação e tutoriais
- Traduções

---

## 📜 Licença

**MIT** — aberto, gratuito e livre para uso, modificação e distribuição.

---

<p align="center">
  Feito com ❤️ pela <a href="https://iabotz.com.br">IA Botz</a> — ecossistema de agentes de IA
</p>

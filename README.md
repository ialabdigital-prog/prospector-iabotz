# Prospector IA Botz

Funil completo de prospecção → redesign → deploy → proposta para negócios locais com site fraco.

Painel web: dispare jobs sem terminal (Google Places / Apify → qualify site → redesign → aaPanel).

## Início rápido

```bash
git clone https://github.com/ialabdigital-prog/prospector-iabotz.git
cd prospector-iabotz
./install.sh
cp prospector-config.example.json prospector-config.json
# preencha maps.google_maps_api_key (ou apify) + auth.secret_key

./prospector setup   # CLI
# ou painel:
./venv/bin/gunicorn -b 127.0.0.1:8765 wsgi:app &
./venv/bin/python worker.py &
# http://localhost:8765  (admin / prospector2026 por padrão via env)
```

## 📋 Comandos Principais

| Comando | Descrição |
|---------|-----------|
| `./prospector` | Menu guiado interativo |
| `./prospector prospectar` | Buscar leads no Google Maps |
| `./prospector redesenhar` | Redesenhar sites dos leads |
| `./prospector publicar` | Deploy no aapanel local |
| `./prospector proposta` | Gerar/enviar propostas |
| `./prospector dashboard` | Gerenciar dashboard |
| `./prospector setup` | Configuração completa |
| `./prospector leads` | Ver leads atuais |

## 🏗️ Arquitetura

```
prospector-iabotz/
├── prospector                 # Entry point (menu guiado)
├── install.sh                 # Instalação automática
├── prospector-config.json     # Configuração central
├── leads.md                   # Leads locais (backup)
├── prospector.db              # SQLite (dashboard)
├── sites/                     # Sites gerados por slug
├── venv/                      # Virtual environment
├── skills/
│   ├── prospeccao-playwright/ # Scraper Playwright (headless)
│   ├── deploy-aapanel/        # Deploy aapanel local
│   ├── redesign-premium/      # Redesign de sites
│   ├── proposta-email/        # Propostas por e-mail
│   ├── contrato-servico/      # Contratos
│   └── dashboard-leads/       # Dashboard SQLite
├── commands/                  # Comandos CLI
└── references/                # Templates e scripts
```

## 🔧 Configuração (prospector-config.json)

```json
{
  "assinatura": { "nome": "", "apresentacao": "", "whatsapp": "" },
  "prospeccao": { 
    "nichos": ["nutricionistas", "psicologos"], 
    "cidade": "São Paulo", 
    "leadsPorBusca": 10 
  },
  "playwright": { "headless": true, "stealth": true },
  "aapanel": { 
    "url": "https://panel.iabotz.online",
    "api_token": "", "usuario": "", "senha": "",
    "dominio_base": "panel.iabotz.online",
    "usar_subpasta": false,
    "ssl_auto": true
  },
  "deploy_target": "aapanel"
}
```

## 🔄 Fluxo de Trabalho

```
1. PROSPECÇÃO (Playwright headless)
   └── Google Maps → Filtros → Leads qualificados → Google Sheets + leads.md + Dashboard

2. REDESIGN
   └── Lead → Site premium → Editor visual → Comparador antes/depois

3. DEPLOY (aapanel local)
   └── Site → aapanel API → Subdomínio → SSL Let's Encrypt → HTTPS verificado

4. PROPOSTA
   └── Página-capa → E-mail com rapport → Rascunho Gmail → Follow-up automático
```

## 🌐 aapanel Local

**Subdomínio por cliente (recomendado):**
```
https://nutricionista-joao.panel.iabotz.online/
https://clinica-psicologia-sp.panel.iabotz.online/
```

**Requisitos do servidor:**
- aapanel instalado em `https://panel.iabotz.online`
- API habilitada (Configurações → API → Gerar token)
- DNS wildcard `*.panel.iabotz.online` → IP do servidor
- Usuário FTP/SSH com acesso a `/www/wwwroot/`
- Porta 22 (SSH) e 443 (HTTPS) abertas

## 📊 Dashboard

```bash
# Iniciar dashboard
./iniciar-dashboard.sh
# Acessar: http://localhost:8765
```

Funcionalidades:
- Kanban drag-drop (novo → redesenhado → publicado → proposta → fechado)
- Edição inline de leads
- Filtros, busca, paginação
- Funil de conversão
- Financeiro (receita, MRR, projeção 12m)
- Contratos (pendente/enviado/assinado/pago)

## 🛠️ Tecnologias

- **Playwright** (Chromium headless) - Prospecção no Google Maps
- **aapanel API** - Deploy, SSL, sites
- **Flask + SQLite** - Dashboard local
- **Paramiko/rsync** - Upload SFTP
- **Python 3.10+**

## 📝 Licença

Uso interno - IA Botz / IALab Digital
# 🚀 Prospector IA Botz

**Discover. Redesign. Publish. Convert.**

> ⚠️ **Project 100% in development** — every contribution, idea, issue, and pull request is more than welcome!  
> 🌐 Check out our AI agent ecosystem at [iabotz.com.br](https://iabotz.com.br)  
> 💡 **Free** — open source, no fees, no paid licenses. Just sharing what we've been building.

---

## 🎯 What is Prospector IA Botz?

A **complete and free** commercial prospecting platform that **discovers leads**, **analyzes digital presence**, **redesigns websites with AI**, **publishes on secure subdomains**, and **prepares commercial proposals** via email and WhatsApp — all in a single web panel.

Inspired by the public project [PROSPECTOR-DE-SITES](https://github.com/ArrecheNeto/PROSPECTOR-DE-SITES), this implementation replaces the static dashboard and original CLI commands with a **full Flask application**, featuring authenticated API, persistent queue, dedicated worker, Kanban board, follow-ups, and native integrations.

---

## 🚀 Overview

**Prospector IA Botz** is an open-source commercial prospecting platform that automates the entire **discovery → qualification → redesign → publishing → outreach** cycle for local businesses with weak digital presence.

The system searches for leads on **Google Maps** by niche and location, analyzes website quality, and if poor, **automatically redesigns with AI** — generating visually unique sites with original KIE images, and prepares commercial proposals via **email (Gmail)** and **WhatsApp (Evolution API/Go)**.

All managed through a **premium web panel** with Kanban, intelligent follow-ups, and multi-provider AI integration.

---

## ✨ Features

### 🔍 Smart Lead Discovery
- **Google Maps** search by niche and city
- Automatic **Apify** complement when results are insufficient
- Intelligent deduplication
- Configurable limits per prospection

### ✅ Automatic Qualification
- Configurable minimum TC score
- Detects non-existent, offline, or low-quality websites
- Strong businesses with invalid site + usable contact = **reconstruction opportunity**
- Classifies mature sites for **source-led** strategy

### 🎨 AI-Powered Redesign (LLM + KIE)
- **32 visual directions** with multiple compositions per style
- Creative brief selected by **niche, history, and LLM**
- **Visual identity extraction** from original site: logo, CSS palette, public images
- **Per-brand variation**: composition, hero, surface, density, rhythm, emphasis
- **Source-led strategy**: preserves navigation, content, articles, FAQ from mature sites
- **Quality gate**: blocks versions losing >30% services, >30% articles, >50% FAQ
- **KIE MCP image generation**: hero 16:9, support 4:5, detail 1:1
- **Animated SVG effects**, floating WhatsApp CTA
- **Responsive**: desktop and mobile

### 📧 Proposals
- **Email**: Gmail integration via Composio — avoids spam, creates real drafts
- **WhatsApp**: via Evolution API or Evolution Go
- **Proposal page** with before/after screenshots
- **Draft mode**: nothing is sent without explicit authorization
- **Safety lock**: validates proposal.html, screenshots, public HTTPS, and images

### 📊 Kanban (Pipeline)
| Stage | Description |
|---|---|
| 🆕 New | Lead discovered and qualified |
| 🎨 Redesigned | AI-generated site ready |
| 🌐 Published | Site live with HTTPS |
| 📧 Proposal | Outreach sent |
| 💬 Replied | Lead responded |
| ✅ Closed | Deal closed (optional value) |
| ❌ Discarded | Disqualified |

### 🔄 Smart Follow-up
- **3 business days** after sending without reply
- Checks Gmail for responses before follow-up
- Max **1 follow-up per channel**
- Email: creates Gmail draft + panel copy
- WhatsApp: draft or send via Evolution
- Individual or batch execution
- Optional daily automatic routine

### 🖥️ Premium Web Panel
- **Dashboard** with live metrics
- **Kanban** drag-and-drop
- **Async jobs** with real-time status
- **Settings** for channels, providers, and routines
- **Complete outreach history**
- Premium design with IA Botz branding

---

## 🏗️ Architecture

```
prospector-iabotz/
├── app/
│   ├── api/              REST APIs for the panel
│   ├── discovery/        Search (Google Maps, Apify) and qualification
│   ├── jobs/             Queue and async runners
│   ├── llm/              Multi-provider router
│   ├── static/           CSS, JS, images
│   └── templates/        Panel HTML
├── skills/
│   ├── deploy-aapanel/   Cloudflare DNS, upload, HTTPS
│   ├── proposta-email/   Email generation and follow-up
│   ├── proposta-whatsapp/ Drafts and Evolution API
│   └── redesign-premium/ Catalog, assets, render, screenshots
├── scripts/              Importers and deploy automation
├── worker.py             Queue consumer (exclusive lock)
├── wsgi.py               Web server entry point
└── prospector            Main CLI
```

---

## ⚡ Quick Install

```bash
git clone https://github.com/ialabdigital-prog/prospector-iabotz.git
cd prospector-iabotz
./install.sh
cp prospector-config.example.json prospector-config.json
```

Configure credentials in the local `prospector-config.json` (never versioned).

Create the first admin:

```bash
export PROSPECTOR_ADMIN_USER='admin'
export PROSPECTOR_ADMIN_PASS='use-a-strong-password'
export PROSPECTOR_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Start the panel and worker:

```bash
./venv/bin/gunicorn -b 127.0.0.1:8765 -w 2 --timeout 120 wsgi:app
./venv/bin/python worker.py
```

Access: `http://127.0.0.1:8765`

---

## 🔐 Security

- **Draft mode by default**: nothing is sent without explicit authorization
- **Outreach safety lock**: validates proposal.html, screenshots, public HTTPS, and images before sending
- **Secrets ignored by Git**: prospector-config.json, *.db, sites/, drafts/, logs/
- **First admin** requires explicit environment credentials
- **Minimum-scope tokens** for Cloudflare, aaPanel, Google, Apify, KIE, LLM
- **Secret scanner** recommended before commits

---

## 🤝 Contributing

**Every contribution is more than welcome!** The project is 100% in development and we want to build together with the community.

### How to contribute

1. **Fork** the repository
2. Create a branch: `git checkout -b my-feature`
3. Make your changes (keep them small and testable)
4. Run checks: `./venv/bin/python -m compileall -q app skills worker.py wsgi.py`
5. Commit and push: `git push origin my-feature`
6. Open a **Pull Request** describing what you did

### Ideas for contributing
- New discovery providers (Bing, Yelp, etc.)
- New redesign styles
- More outreach integrations (Telegram, SMS)
- Web panel improvements
- Automated tests
- Documentation and tutorials
- Translations

---

## 📜 License

**MIT** — open, free, and libre for use, modification, and distribution.

---

<p align="center">
  Made with ❤️ by <a href="https://iabotz.com.br">IA Botz</a> — AI agent ecosystem
</p>

# 🚀 Prospector IA Botz

**Descubre. Rediseña. Publica. Convierte.**

> ⚠️ **Proyecto 100% en desarrollo** — ¡toda contribución, idea, issue y pull request es más que bienvenida!  
> 🌐 Conoce nuestro ecosistema de agentes de IA en [iabotz.com.br](https://iabotz.com.br)  
> 💡 **Gratuito** — código abierto, sin tarifas, sin licencias pagas. La idea es compartir lo que venimos construyendo.

---

## 🎯 ¿Qué es Prospector IA Botz?

Una plataforma **completa y gratuita** de prospección comercial que **descubre leads**, **analiza la presencia digital**, **rediseña sitios web con IA**, **publica en subdominios seguros** y **prepara propuestas comerciales** por correo electrónico y WhatsApp — todo en un solo panel web.

Inspirado en el proyecto público [PROSPECTOR-DE-SITES](https://github.com/ArrecheNeto/PROSPECTOR-DE-SITES), esta implementación reemplaza el dashboard estático y los comandos CLI originales con una **aplicación Flask completa**, con API autenticada, cola persistente, worker dedicado, Kanban, seguimientos e integraciones nativas.

---

## 🚀 Visión General

**Prospector IA Botz** es una plataforma open-source de prospección comercial que automatiza todo el ciclo de **descubrimiento → calificación → rediseño → publicación → outreach** para negocios locales con presencia digital débil.

El sistema busca leads en **Google Maps** por nicho y localidad, analiza la calidad del sitio web, y si es malo, **rediseña automáticamente con IA** — generando sitios visualmente únicos con imágenes originales vía KIE, y prepara propuestas comerciales por **correo electrónico (Gmail)** y **WhatsApp (Evolution API/Go)**.

Todo gestionado desde un **panel web premium** con Kanban, seguimientos inteligentes e integración con múltiples proveedores de IA.

---

## ✨ Funcionalidades

### 🔍 Descubrimiento Inteligente de Leads
- Búsqueda en **Google Maps** por nicho y ciudad
- Complemento automático con **Apify** si resultados insuficientes
- Deduplicación inteligente
- Límites configurables por prospección

### ✅ Calificación Automática
- Puntuación TC mínima configurable
- Detecta sitios inexistentes, caídos o de baja calidad
- Negocios fuertes con sitio inválido + contacto útil = **oportunidad de reconstrucción**
- Clasifica sitios maduros para estrategia **source-led**

### 🎨 Rediseño con IA (LLM + KIE)
- **32 direcciones visuales** con múltiples composiciones por estilo
- Briefing creativo seleccionado por **nicho, historial y LLM**
- **Extracción de identidad visual** del sitio original: logo, paleta CSS, imágenes públicas
- **Variación por marca**: composición, hero, superficie, densidad, ritmo, énfasis
- **Estrategia source-led**: preserva navegación, contenido, artículos, FAQ de sitios maduros
- **Quality gate**: bloquea versiones que pierden >30% servicios, >30% artículos, >50% FAQ
- **Generación de imágenes vía KIE MCP**: hero 16:9, soporte 4:5, detalle 1:1
- **Efectos SVG animados**, CTA de WhatsApp flotante
- **Responsivo**: escritorio y móvil

### 📧 Propuestas
- **Correo**: integración con **Gmail vía Composio** — evita spam, crea drafts reales
- **WhatsApp**: vía **Evolution API** o **Evolution Go**
- **Página de propuesta** con captura del antes/después
- **Modo borrador**: nada se envía sin autorización explícita
- **Bloqueo de seguridad**: valida proposal.html, screenshots, HTTPS público e imágenes

### 📊 Kanban (Pipeline)
| Etapa | Descripción |
|---|---|
| 🆕 Nuevo | Lead descubierto y calificado |
| 🎨 Rediseñado | Sitio generado con IA |
| 🌐 Publicado | Sitio en línea con HTTPS |
| 📧 Propuesta | Outreach enviado |
| 💬 Respondió | Lead respondió |
| ✅ Cerrado | Negocio cerrado (valor opcional) |
| ❌ Descartado | Descalificado |

### 🔄 Seguimiento Inteligente
- **3 días hábiles** después del envío sin respuesta
- Verifica respuestas en Gmail antes del seguimiento
- Máximo **1 seguimiento por canal**
- Correo: crea borrador en Gmail + copia en el panel
- WhatsApp: borrador o envío vía Evolution
- Ejecución individual o por lote
- Rutina diaria automática opcional

### 🖥️ Panel Web Premium
- **Dashboard** con métricas en vivo
- **Kanban** drag-and-drop
- **Jobs asíncronos** con estado en tiempo real
- **Configuraciones** de canales, proveedores y rutinas
- **Historial completo** de outreach
- Diseño premium con marca IA Botz

---

## 🏗️ Arquitectura

```
prospector-iabotz/
├── app/
│   ├── api/              APIs REST del panel
│   ├── discovery/        Búsqueda (Google Maps, Apify) y calificación
│   ├── jobs/             Cola y runners asíncronos
│   ├── llm/              Enrutador multi-proveedor
│   ├── static/           CSS, JS, imágenes
│   └── templates/        HTML del panel
├── skills/
│   ├── deploy-aapanel/   DNS Cloudflare, subida, HTTPS
│   ├── proposta-email/   Generación de correo y seguimiento
│   ├── proposta-whatsapp/ Borradores y Evolution API
│   └── redesign-premium/ Catálogo, assets, render, capturas
├── scripts/              Importadores y automatización de deploy
├── worker.py             Consumidor de cola (bloqueo exclusivo)
├── wsgi.py               Entrada del servidor web
└── prospector            CLI principal
```

---

## ⚡ Instalación Rápida

```bash
git clone https://github.com/ialabdigital-prog/prospector-iabotz.git
cd prospector-iabotz
./install.sh
cp prospector-config.example.json prospector-config.json
```

Configure las credenciales en el archivo local `prospector-config.json` (nunca versionado).

Cree el primer administrador:

```bash
export PROSPECTOR_ADMIN_USER='admin'
export PROSPECTOR_ADMIN_PASS='use-una-contraseña-fuerte'
export PROSPECTOR_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Inicie el panel y el worker:

```bash
./venv/bin/gunicorn -b 127.0.0.1:8765 -w 2 --timeout 120 wsgi:app
./venv/bin/python worker.py
```

Acceda: `http://127.0.0.1:8765`

---

## 🔐 Seguridad

- **Modo borrador por defecto**: nada se envía sin autorización explícita
- **Bloqueo de seguridad de outreach**: valida proposal.html, screenshots, HTTPS público e imágenes antes de enviar
- **Secretos ignorados por Git**: prospector-config.json, *.db, sites/, drafts/, logs/
- **Primer admin** requiere credenciales explícitas de entorno
- **Tokens con alcance mínimo** para Cloudflare, aaPanel, Google, Apify, KIE, LLM
- **Escáner de secretos** recomendado antes de commits

---

## 🤝 Contribución

**¡Toda contribución es más que bienvenida!** El proyecto está 100% en desarrollo y queremos construir junto con la comunidad.

### Cómo contribuir

1. Haga un **fork** del repositorio
2. Cree una rama: `git checkout -b mi-feature`
3. Haga sus cambios (manténgalos pequeños y comprobables)
4. Ejecute las verificaciones: `./venv/bin/python -m compileall -q app skills worker.py wsgi.py`
5. Commit y push: `git push origin mi-feature`
6. Abra un **Pull Request** describiendo lo que hizo

### Ideas para contribuir
- Nuevos proveedores de descubrimiento (Bing, Yelp, etc.)
- Nuevos estilos de rediseño
- Más integraciones de outreach (Telegram, SMS)
- Mejoras en el panel web
- Tests automatizados
- Documentación y tutoriales
- Traducciones

---

## 📜 Licencia

**MIT** — abierto, gratuito y libre para uso, modificación y distribución.

---

<p align="center">
  Hecho con ❤️ por <a href="https://iabotz.com.br">IA Botz</a> — ecosistema de agentes de IA
</p>

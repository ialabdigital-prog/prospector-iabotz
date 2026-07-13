---
name: dashboard-leads
description: Pipeline comercial do Prospector IA Botz, incluindo Kanban, leads, outreach, follow-ups, contratos e financeiro no painel Flask.
---

# Dashboard de leads

O dashboard oficial é a aplicação Flask iniciada por `wsgi.py` e servida em `http://127.0.0.1:8765`. Não existe um segundo dashboard HTML estático.

## Fonte da verdade

- `prospector.db`: leads, jobs, eventos, usuários e histórico de outreach.
- `app/api/`: API autenticada usada pelo painel.
- `app/templates/app.html` e `app/static/`: interface.
- `worker.py`: jobs assíncronos e rotina diária opcional.

## Pipeline

`novo | redesenhado | publicado | proposta | respondeu | fechado | descartado`

- `novo`: lead qualificado.
- `redesenhado`: site criado e revisável.
- `publicado`: site e DNS no ar.
- `proposta`: contato realmente enviado ou marcado manualmente como enviado.
- `respondeu`: resposta detectada pelo Gmail ou registrada manualmente.
- `fechado`: acordo confirmado manualmente.
- `descartado`: removido do pipeline ativo sem apagar o histórico.

O Kanban grava mudanças diretamente em `PUT /api/leads/<slug>`. Mover manualmente para `proposta` inicia a contagem de follow-up; mover para `respondeu` interrompe follow-ups.

## Follow-up

- Elegível depois de 3 dias úteis desde o envio real.
- No máximo um follow-up por canal.
- Respostas do Gmail são verificadas antes de criar o follow-up de e-mail.
- Em `envio.modo: rascunho`, nenhuma mensagem é enviada automaticamente.
- Datas ficam em campos próprios (`emailSentAt`, `whatsappSentAt`, `followupEmailAt`, `followupWhatsAppAt`, `respondedAt`), não em texto livre.

## Inicialização

```bash
./iniciar-dashboard.sh
```

Web e worker devem permanecer ativos. O painel inclui as telas Pipeline, Leads, Follow-ups, Mensagens, Outreach, Jobs e Config.

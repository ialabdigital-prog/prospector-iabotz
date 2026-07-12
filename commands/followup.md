---
description: Follow-up automático para leads que não responderam à proposta — envia e-mail curto e gentil após 3+ dias úteis
argument-hint: "[nome do cliente ou todos]"
---

Follow-up de proposta seguindo a skill `proposta-email`.

## Regras

- **1 único follow-up por lead** — após 3+ dias úteis sem resposta ao e-mail original.
- Curto, gentil: "Oi [Nome], conseguiste dar uma olhada na página que te mandei? Qualquer dúvida tô à disposição."
- Mesmo thread do e-mail original (reply) se possível; senão novo e-mail com assunto "Re: [assunto original]".
- Modo rascunho (padrão) ou envio direto — igual à proposta original.
- Registre no `leads.md` + dashboard: data do follow-up.

## Execução

1. Determine alvos: `$ARGUMENTS` ou leads com status `proposta enviada` há ≥ 3 dias úteis sem status `respondeu`/`fechado`.
2. Para cada um, crie/envi e-mail de follow-up.
3. Atualize registros.

## Saída

Liste follow-ups criados/enviados. Sugira `/respostas` para checar replies.
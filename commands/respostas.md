---
description: Verifica no Gmail se propostas foram enviadas ou respondidas e atualiza o pipeline.
argument-hint: "[slug|todos]"
---

Execute o job `respostas` pelo painel ou worker.

1. Consulte leads `publicado`/`proposta` com e-mail.
2. Use Composio Gmail para detectar mensagens em `Sent` destinadas ao lead.
3. Ao detectar envio, marque `emailSentAt`, `dataProposta` e status `proposta`.
4. Busque mensagens recebidas do lead depois do envio.
5. Ao detectar resposta, marque `respondeu`, `respondedAt` e registre o evento.
6. Nunca responda automaticamente nem marque `fechado`.

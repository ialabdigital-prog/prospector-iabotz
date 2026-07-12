---
description: Editor visual para ajustes manuais nas páginas redesenhadas — edita textos/imagens direto no navegador e exporta HTML final
argument-hint: "[nome do cliente]"
---

Edite páginas no editor visual seguindo a skill `redesign-premium`.

## Uso

1. Receba `$ARGUMENTS` (nome do cliente) ou pergunte qual lead em status `redesenhado` ou `publicado` editar.
2. Abra `sites/[slug]/editor.html` no navegador (Claude in Chrome) — o editor carrega o `index.html` em iframe + toolbar lateral.
3. Ferramentas do editor:
   - **Clique para editar**: qualquer texto vira editável in-place (contentEditable)
   - **Imagens**: clique → troca por upload ou URL
   - **Cores/tipografia**: painel lateral com variáveis CSS (cores da marca, fontes, espaçamento)
   - **Seções**: add/remove/reorder via drag-and-drop
   - **Preview mobile/desktop**: toggle de viewport
   - **Exportar**: botão "Salvar HTML final" → baixa `index.html` atualizado e substitui o original
4. Se o site já estava `publicado`, pergunte se quer republicar (`/publicar`) após a edição.

## Saída

Confirme alterações salvas. Se republicar necessário, guie para `/publicar`.
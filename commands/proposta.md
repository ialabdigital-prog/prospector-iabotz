---
description: Escreve e envia a proposta comercial por e-mail para um lead prospectado — e-mail de apresentação da nova versão do site, com rapport e sem preço
argument-hint: "[nome do cliente ou todos]"
---

Escreva e envie proposta por e-mail seguindo a skill `proposta-email`.

## Passos

1. Determine para quem: `$ARGUMENTS` (um cliente ou "todos"), ou liste leads com status `publicado` em `leads.md` e pergunte.
2. Para cada lead:
   - Monte o e-mail seguindo os **Princípios** e **Estrutura** da skill:
     - **Assunto**: pergunta pessoal e específica, ≤ 60 chars, sem cara de marketing. Ex.: `Dra. [Nome], posso te mostrar uma coisa sobre seu site?`
     - **Parágrafo 1**: quem encontrou + elogio ESPECÍFICO e verificável (nota no Google, avaliação real, credencial do site).
     - **Parágrafo 2**: observação sobre o site atual (1-2 pontos objetivos — "notei que no celular o site fica difícil de ler", "o botão de WhatsApp não aparece na primeira tela").
     - **Parágrafo 3**: "preparei uma nova versão, já no ar" + **O ÚNICO LINK** do e-mail: a página-capa (`https://[domínio]/[slug]/proposta.html`), que mostra antes/depois lado a lado. Se a capa não existir, linkar a página nova direto.
     - **Parágrafo 4**: CTA — abrir no celular também, responder com a impressão.
     - **Assinatura**: nome, apresentação e WhatsApp do config (assinatura completa humaniza e reduz suspeita).
   - **Checklist anti-spam (BLOQUEANTE — rodar antes de criar o rascunho)**:
     - [ ] 1 link só (a página-capa). Dois no máximo se incluir o site antigo — nunca mais que isso.
     - [ ] Sem encurtador de URL (bit.ly etc. = spam na certa). Link é o domínio real, com `https://`.
     - [ ] Link como âncora HTML com texto visível limpo: `<a href="https://[domínio]/[pastaBase]/[slug]/proposta.html">https://[domínio]/[pastaBase]/[slug]/proposta.html</a>` — texto visível = a URL limpa montada a partir do config (nunca copiada de outro e-mail). O redirect do Google fica só no href invisível, como em qualquer e-mail do Gmail. Depois de criar, confira o rascunho: o texto visível deve começar em `https://[domínio do config]`.
     - [ ] Domínio limpo e humano. Se o domínio for técnico ou temporário, pare e configure um domínio próprio apresentável.
     - [ ] Sem palavras-gatilho: grátis, promoção, imperdível, oferta, desconto, clique aqui, 100%, garantido, urgente.
     - [ ] Sem CAIXA ALTA no assunto, sem "!!", sem emoji no assunto.
     - [ ] Texto simples — corpo HTML minimalista (só parágrafos e a âncora do link; zero cores, botões, imagens ou anexos) (anexo de desconhecido aumenta score de spam E medo de abrir; a capa no link substitui o preview).
     - [ ] Assunto ≤ 60 caracteres, formulado como pergunta ou frase pessoal com o nome do negócio.
     - [ ] Primeira linha 100% personalizada (nome + fato real das avaliações) — filtros de spam e humanos reconhecem template genérico.
     - [ ] Remetente = conta Gmail pessoal ativa do usuário (já tem SPF/DKIM do Google). Nunca sugerir disparo em massa: os envios são 1 a 1, poucos por dia — padrão humano.
3. **Envio**:
   - Modo **rascunho** (padrão): criar via conector do Gmail (`create_draft`) com destinatário, assunto e corpo prontos. Avisar o usuário para revisar antes de enviar.
   - Modo **enviar direto**: se o conector não suportar envio, abrir o Gmail web via Claude in Chrome, ou criar o rascunho e avisar.
   - Nunca enviar para lead sem e-mail confirmado; nesses casos, sugerir contato via WhatsApp com a mesma mensagem adaptada.
4. **Página-capa** (o que o cliente vê ao clicar):
   - O link do e-mail leva à página-capa gerada no `/publicar` (template em `references/capa-proposta-template.html`): nome do cliente no topo, antes/depois lado a lado e a assinatura do usuário. Ela existe para dar credibilidade ao clique — o cliente vê o próprio negócio, não um link estranho. Exigências: servida em `https://`, personalizada com dados reais, sem pedido de dado pessoal nenhum.
5. **Depois do envio**:
   - Registrar no banco/`leads.md` (status + data) e no dashboard. As respostas são verificadas pelo comando `/respostas` (Gmail via conector) — sugira ao usuário agendar a verificação diária. Follow-up pelo `/followup` após 3+ dias úteis sem resposta (1 único follow-up por lead: curto, gentil, "conseguiu ver a página?").

## Saída

Confirme quantos e-mails foram criados/enviados, com destinatários e assuntos. Sugira `/respostas` para monitorar.

---
description: Publica as páginas redesenhadas no aapanel e retorna as URLs públicas com HTTPS
argument-hint: "[nome do cliente ou todos]"
---

Publique páginas no aapanel seguindo a skill `deploy-aapanel`.

## Passos

1. Leia `prospector-config.json`. Se os dados do aapanel não estiverem preenchidos, colete-os agora (url, api_token, usuário, senha, dominio_base, pasta_base, usar_subdominio) — não prossiga sem eles.
2. Determine o que publicar: `$ARGUMENTS` (um cliente ou "todos"), ou liste as páginas com status `redesenhado` em `leads.md` e pergunte.
3. **Gere a página-capa de cada cliente**: preencha `skills/proposta-email/references/capa-proposta-template.html` com os dados do lead + assinatura do config e salve como `sites/[slug]/proposta.html`. É ela que vai no e-mail de proposta.
4. **Publique seguindo a skill `deploy-aapanel`**, nesta ordem:
   - Tente a API direta do aapanel: crie site → SSL Let's Encrypt → upload via SFTP/rsync
   - Se a API falhar, use o publicador local (mesmo fluxo do HostGator): garanta os 4 arquivos do publicador na pasta, monte a `fila-publicacao.txt` com página (`index.html`) e capa (`proposta.html`) de cada cliente e aguarde ~90s: a tarefa agendada publica sozinha (confira a fila renomeada e o `publicador-log.txt`). Se a tarefa ainda não foi instalada, peça o duplo clique único no `instalar-publicador.command` (Mac) ou `.bat` (Windows).
5. **Verificação HTTPS (bloqueante)**: abra cada URL com `https://` e confirme que carrega com cadeado válido. Se o HTTPS falhar, siga a seção "HTTPS obrigatório" da skill `deploy-aapanel` (AutoSSL no aapanel) antes de considerar publicado — link `http://` NUNCA vai para cliente.
6. Atualize `leads.md` e o banco do dashboard: status `publicado` + URL pública nova.

## Saída

Liste, por cliente: URL da página nova e URL da capa (`.../proposta.html`), ambas testadas em https. Sugira o próximo passo: `/proposta` para enviar os e-mails.
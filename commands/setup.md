---
description: Configura o plugin — assinatura, preferências, conexão com aapanel, Cloudflare e Playwright (roda uma vez)
---

Configure o ambiente do Prospector de Sites. Siga esta ordem:

## 1. Pasta de trabalho

Verifique se há uma pasta do usuário conectada. Se não houver, peça para conectar uma pasta (ex.: "Clientes") usando a ferramenta de solicitação de pasta — tudo (config, leads e sites criados) será salvo nela para persistir entre sessões.

## 2. Verificar config existente

Procure `prospector-config.json` na pasta conectada. Se existir, mostre um resumo (sem exibir senhas/tokens) e pergunte o que o usuário quer atualizar. Se não existir, colete os dados abaixo.

## 3. Dados do usuário (perguntar via formulário/perguntas)

Colete:

- **Assinatura da proposta**: nome completo, como quer se apresentar (ex.: "Especialista em automação e growth digital para negócios locais") e WhatsApp/telefone de contato.
- **Nichos padrão de prospecção**: sugira nutricionistas, psicólogos, advogados, psiquiatras, dentistas, médicos, clínicas, personal trainers, estéticas, escritórios contabilidade como ponto de partida, mas deixe o usuário editar livremente.
- **Cidade/região padrão**.
- **Leads qualificados por busca**: padrão 10.
- **Modo de envio da proposta**: padrão "criar rascunho no Gmail para revisão" (recomendado). Alternativa: enviar direto.

## 4. Conexão com o aapanel

Pergunte se o usuário já tem o aapanel instalado e acessível.

- **Se ainda não tem**: explique brevemente que ele precisa de um VPS/servidor com aapanel instalado (gratuito), domínio próprio apontado para o servidor, e que depois de configurado deve voltar e rodar `/setup` de novo. Salve o config parcial e encerre.
- **Se já tem**: **NÃO colete nenhum dado do aapanel pelo chat** (nem URL, nem token, nem usuário SSH — e JAMAIS a senha). Tudo vai num lugar só, a aba Configurações do dashboard:
  1. Instrua: abra o dashboard (`python3 dashboard-server.py` na pasta conectada) → aba **Configurações** → seção **Conexão aapanel**.
  2. Lá ele preenche os 5 campos + senha SSH: URL do painel (ex.: `https://panel.seudominio.com:8888`), Token API (Painel → API → Gerar token), Domínio base (ex.: `seudominio.com`), Usuário SSH, Senha SSH. Clica em "Salvar conexão" → tudo vai do navegador direto pro `prospector-config.json` no computador dele, sem passar pelo chat.
  3. Peça para ele avisar quando salvar ("salvei") — aí você LÊ o config (verificando que os campos estão preenchidos, sem nunca exibir a senha/token) e roda o teste de conexão.

  Nunca exiba, imprima ou registre a senha/token em nenhuma saída. Se ele preferir, editar o `prospector-config.json` na mão também vale.

## 5. Conexão com Cloudflare (DNS automático para subdomínios)

**NOVO**: Para criar subdomínios automáticos para cada prospect (ex.: `nutricionista-joao.panel.iabotz.online`), usamos a API do Cloudflare para criar o registro CNAME automaticamente.

Pergunte se o usuário tem conta no Cloudflare com o domínio base (ex.: `iabotz.online`) gerenciado lá.

- **Se não tem**: explique que o DNS será manual (o usuário cria o CNAME manualmente no painel DNS) — o deploy ainda funciona mas o SSL só sai depois que o DNS propagar.
- **Se tem**: **NÃO colete token/email pelo chat**. Tudo vai na aba **Configurações** do dashboard → seção **Conexão Cloudflare**:
  1. Instrua: dashboard → Configurações → seção **Conexão Cloudflare**.
  2. Preenche: API Token (Cloudflare → My Profile → API Tokens → Create Token com permissões DNS:Edit), Email da conta, Zona (domínio base, ex.: `iabotz.online`), Proxy (on/off — recomendado ON para proteção DDoS).
  3. Clica "Salvar conexão" → vai direto pro `prospector-config.json`.

  Com Cloudflare configurado, o `/publicar` cria automaticamente o CNAME `slug.panel.iabotz.online` → `panel.iabotz.online` e aguarda DNS propagar antes de solicitar SSL.

## 6. Configuração do Playwright (prospecção headless)

Pergunte se deseja usar prospecção via Playwright no servidor (padrão: sim, não precisa do Chrome do usuário).

- Se sim, confirme as configurações no bloco `playwright` do config (headless, user-agent, rate limit, stealth mode, proxy opcional).
- Explique que na primeira execução pode pedir para resolver CAPTCHA/login manualmente uma vez — o estado fica salvo em `playwright-state.json` para próximas rodadas.

## 7. Salvar e testar

Salve tudo em `prospector-config.json` na pasta conectada, neste formato:

```json
{
  "assinatura": { "nome": "", "apresentacao": "", "whatsapp": "" },
  "prospeccao": { "nichos": ["nutricionistas", "psicologos", "advogados", "psiquiatras"], "cidade": "", "leadsPorBusca": 10, "notaMinima": 4.7, "avaliacoesMinimas": 40 },
  "envio": { "modo": "rascunho" },
  "aapanel": { "url": "", "api_token": "", "usuario": "", "senha": "", "dominio_base": "", "pasta_base": "clientes", "usar_subdominio": true, "ssl_auto": true, "php_version": "82" },
  "cloudflare": { "api_token": "", "email": "", "zone": "iabotz.online", "proxied": true },
  "playwright": { "headless": true, "browser": "chromium", "timeout_ms": 30000, "delay_entre_requisicoes_ms": 2000, "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36...", "viewport": { "width": 1366, "height": 768 }, "proxy": "", "stealth": true },
  "dashboard": { "porta": 8765, "host": "0.0.0.0" }
}
```

Se os dados do aapanel/Cloudflare foram informados, teste as conexões seguindo as skills `deploy-aapanel` e `cloudflare_client`: publique uma página `teste.html` simples ("Funcionou!") no domínio de teste e informe a URL pública ao usuário. Se o teste falhar, diagnostique (credenciais, token, conectividade SSH, DNS) antes de concluir.

## 8. Dashboard inicial

Siga a seção "Setup" da skill `dashboard-leads`: copie `dashboard-server.py` e `iniciar-dashboard.sh` para a raiz da pasta conectada, crie o banco `prospector.db` (schema da skill) e gere o `dashboard.html` do template. Explique ao usuário: executar `iniciar-dashboard.sh` abre o painel completo em http://localhost:8765 com edição/exclusão salvando no banco (requer Python no servidor; sem ele, o dashboard.html abre no modo leitura).

## 9. Entregar o manual e os scripts

Copie da pasta do plugin para a pasta conectada (sobrescrevendo versões antigas): `manual.html` (manual do usuário) e os arquivos do publicador aapanel (`publicar-aapanel.py`, `instalar-publicador.sh`) — mais o iniciador do dashboard certo (`iniciar-dashboard.sh`). Peça UM comando para instalar o publicador (registra no systemd/cron — única vez na vida; o teste de conexão do item 7 pode usar esse fluxo). Apresente o `manual.html` ao usuário com a frase: "Esse é o seu manual — guarda ele que responde 90% das dúvidas."

## 10. Encerrar

Confirme o que foi salvo e explique o ciclo (guiando **SEMPRE** o próximo passo ao fim de cada comando): `/prospectar` → `/redesenhar` → `/publicar` → `/proposta`, com `/editor` opcional para ajustes manuais e o `dashboard.html` como painel de controle de tudo.
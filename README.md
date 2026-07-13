# Prospector IA Botz

Plataforma de prospecção comercial que reúne descoberta de negócios, qualificação de sites, criação de redesigns com IA, publicação e preparação de outreach em um único painel.

O fluxo foi inspirado no projeto público [PROSPECTOR-DE-SITES](https://github.com/ArrecheNeto/PROSPECTOR-DE-SITES). Esta implementação substitui o dashboard estático e os comandos orientativos originais por uma aplicação Flask, API autenticada, fila persistente, worker, integrações e acompanhamento operacional próprios.

O projeto foi desenhado para equipes que identificam negócios locais com presença digital fraca e precisam transformar essa oportunidade em uma demonstração visual pronta para revisão. O envio de mensagens fica em **modo rascunho por padrão**: nenhuma automação deve contactar um lead sem configuração e decisão explícitas do operador.

## Principais recursos

- Descoberta de leads via Google Places e Apify, com deduplicação e complemento automático de resultados.
- Qualificação de sites inexistentes, indisponíveis ou com sinais de baixa qualidade.
- Catálogo com 32 direções visuais e múltiplas composições por estilo.
- Briefing criativo selecionado por nicho, histórico e LLM, com fallback determinístico.
- Identidade visual extraída do site original: logo, paleta CSS, imagens públicas e conteúdo factual.
- Variação por marca e regeneração: composição, hero, superfície, densidade, ritmo e ênfase sem repetir `style + layout`.
- Geração de copy sem inventar credenciais, serviços, avaliações ou depoimentos.
- Imagens novas via KIE para hero, editorial e detalhe, com manifesto de assets.
- Renderização responsiva com efeitos SVG, movimento reduzido e CTA de WhatsApp.
- Capturas de desktop e mobile para revisão visual.
- Deploy em aaPanel, DNS via Cloudflare e validação de HTTPS.
- Rascunhos de e-mail e WhatsApp; Evolution API disponível somente quando o modo de envio é habilitado.
- Painel Flask com funil, métricas, jobs assíncronos, configurações e histórico de outreach.
- Kanban drag-and-drop com etapas `novo`, `redesenhado`, `publicado`, `proposta`, `respondeu`, `fechado` e `descartado`.
- Detecção de mensagens enviadas e respostas no Gmail via Composio.
- Follow-up único por canal após três dias úteis, com verificação prévia de respostas.
- Worker com lock de processo para impedir jobs duplicados e consumo duplicado de APIs.

## Fluxo

```text
Descoberta -> Qualificação -> Direção criativa -> Redesign
          -> QA visual -> Publicação -> Outreach -> Resposta/Follow-up
```

1. O motor busca candidatos e normaliza os dados públicos encontrados.
2. A qualificação identifica oportunidades, inclusive sites inválidos ou fora do ar.
3. O catálogo e o LLM escolhem uma direção visual não usada recentemente para o lead.
4. O redesign preserva fatos verificáveis, gera assets e grava o site em `sites/<slug>/`.
5. O Playwright produz screenshots para conferência em desktop e mobile.
6. A publicação cria um hostname seguro, envia os arquivos e valida DNS/HTTPS.
7. O outreach produz arquivos revisáveis em `drafts/`; o envio real exige `envio.modo: "envio"`.
8. O Gmail confirma envios/respostas e o Kanban mantém o estágio comercial.
9. Após três dias úteis sem resposta, o sistema prepara no máximo um follow-up por canal.

## Arquitetura

```text
app/
  api/                 APIs do painel
  discovery/           busca e qualificação
  jobs/                fila e runners assíncronos
  llm/                 roteamento de provedores
  static/, templates/  interface web
skills/
  deploy-aapanel/       DNS, upload e HTTPS
  proposta-email/      geração de e-mail e follow-up
  proposta-whatsapp/   drafts e integração Evolution
  redesign-premium/    catálogo, assets, render e screenshots
scripts/               importadores e automação de deploy
worker.py               consumidor da fila com lock exclusivo
wsgi.py                 entrada do servidor web
```

O estado operacional é local e não é versionado:

- `prospector-config.json`: chaves e configuração ativa.
- `prospector.db`: banco SQLite.
- `sites/`: páginas e imagens geradas.
- `drafts/`: mensagens e e-mails preparados.
- `logs/`: logs de execução.

## Requisitos

- Linux ou macOS.
- Python 3.10 ou superior.
- Chromium do Playwright.
- Credencial de ao menos um mecanismo de descoberta: Google Maps ou Apify.
- Provedor LLM configurado para variações e copy assistida.
- Opcionais: KIE, aaPanel, Cloudflare, Evolution API e Composio.

## Instalação

```bash
git clone https://github.com/ialabdigital-prog/prospector-iabotz.git
cd prospector-iabotz
./install.sh
cp prospector-config.example.json prospector-config.json
```

Edite apenas o arquivo local `prospector-config.json`. Ele está no `.gitignore` e nunca deve ser commitado.

Para criar o primeiro administrador, defina credenciais explícitas:

```bash
export PROSPECTOR_ADMIN_USER='admin'
export PROSPECTOR_ADMIN_PASS='use-uma-senha-longa-e-unica'
export PROSPECTOR_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Inicie web e worker em terminais separados:

```bash
./venv/bin/gunicorn -b 127.0.0.1:8765 -w 2 --timeout 120 wsgi:app
./venv/bin/python worker.py
```

Abra `http://127.0.0.1:8765`.

## Configuração

O arquivo `prospector-config.example.json` contém somente placeholders seguros. As seções mais importantes são:

| Seção | Finalidade |
|---|---|
| `prospeccao` | Nichos, cidade, limites e critérios mínimos |
| `maps` | Credenciais Google Maps/Apify e engine |
| `llm` | Provedor, modelo e chave do roteador |
| `redesign` | Direção, KIE, modelo de imagem e efeitos |
| `aapanel` | Endpoint, token, domínio e diretórios de deploy |
| `cloudflare` | Zona, token DNS e proxy |
| `envio` | Modo seguro, canais e Evolution API |
| `composio` | Integração opcional com Gmail |
| `auth` | Secret da sessão web |

Exemplo mínimo para desenvolvimento:

```json
{
  "maps": {
    "google_maps_api_key": "",
    "apify_api_key": "",
    "engine": "auto"
  },
  "llm": {
    "default_provider": "openrouter",
    "openrouter_api_key": "",
    "openrouter_model": "openai/gpt-4o-mini"
  },
  "envio": {
    "modo": "rascunho",
    "canais": ["email"]
  },
  "auth": {
    "secret_key": "substitua-em-producao"
  }
}
```

## CLI

```bash
./prospector setup
./prospector prospectar
./prospector redesenhar <slug|todos>
./prospector publicar <slug|todos>
./prospector proposta <slug|todos>
./prospector proposta-whatsapp <slug|todos>
./prospector followup
./prospector followup-whatsapp
./prospector respostas [slug|todos]
./prospector dashboard
```

Para reconstruir o HTML e as screenshots com o briefing e assets já existentes, sem consumir novos créditos KIE:

```bash
./prospector redesenhar <slug> --render-only
```

## Provedores

### Descoberta

`maps.engine` aceita `google`, `apify` ou `auto`. No modo `auto`, resultados insuficientes do Google podem ser complementados pelo Apify e deduplicados antes da qualificação.

### LLM

O roteador suporta os provedores configurados no projeto e usa fallback quando um CLI local solicitado não está disponível. Não coloque chaves em argumentos, logs ou arquivos versionados.

### Imagens

Com `redesign.image_provider: "kie_mcp"`, cada nova direção visual solicita assets versionados em três proporções. Use `--render-only` quando a intenção for apenas aplicar correções de renderização aos assets existentes.

### Outreach

O padrão é:

```json
{ "envio": { "modo": "rascunho" } }
```

Nesse modo, e-mails e WhatsApp são gravados em `drafts/` e nenhuma chamada de envio é feita. Para envio real, configure o provedor, revise o conteúdo e altere deliberadamente o modo para `envio`.

### Kanban e follow-up

O painel possui uma tela `Pipeline` com drag-and-drop. Mover manualmente um lead para `Proposta` confirma que o contato foi enviado e inicia o prazo de três dias úteis. A detecção de uma resposta move o lead para `Respondeu` e cancela novos follow-ups.

A tela `Follow-ups` permite:

- Ver os leads elegíveis e os dias úteis transcorridos.
- Verificar respostas no Gmail antes de contactar novamente.
- Preparar follow-up individual ou em lote.
- Ativar uma rotina diária opcional em `Config > Canais`.

Cada canal recebe no máximo um follow-up. Com `envio.modo: "rascunho"`, a rotina automática apenas cria drafts e nunca envia mensagens.

## Deploy

O deploy público usa variáveis e configuração do seu próprio ambiente. Nunca registre domínio, endereço do servidor ou credenciais no código.

```bash
export PROSPECTOR_DOMAIN='prospector.example.com'
export PROSPECTOR_ADMIN_USER='admin'
export PROSPECTOR_ADMIN_PASS='senha-forte'
sudo -E ./scripts/deploy-panel.sh
```

Para sites de prospects, configure aaPanel e Cloudflare no arquivo local. O hostname público é derivado e validado separadamente do slug interno; rótulos DNS longos são encurtados de forma determinística.

## Segurança

- Segredos e estado local são ignorados pelo Git.
- Não use valores reais em `prospector-config.example.json`, documentação, fixtures ou screenshots.
- Mantenha `envio.modo` como `rascunho` em desenvolvimento e testes.
- Use tokens com escopo mínimo para Cloudflare, aaPanel, Google, Apify, KIE e LLM.
- Troque `PROSPECTOR_SECRET_KEY` e a senha inicial em cada ambiente.
- Restrinja o painel atrás de HTTPS e de uma política de acesso apropriada.
- Antes de publicar alterações, execute um scanner de segredos e revise `git diff --cached`.

Se uma credencial já tiver sido commitada, removê-la do arquivo não basta: revogue-a imediatamente e limpe o histórico com uma ferramenta apropriada.

## Verificação

Validação básica do código:

```bash
./venv/bin/python -m compileall -q app skills worker.py wsgi.py
node --check app/static/js/panel.js
```

Health check local:

```bash
curl --fail http://127.0.0.1:8765/health
```

Antes de um deploy, valide também:

- Login e criação do primeiro administrador.
- Descoberta com limite pequeno.
- Redesign e screenshots em desktop/mobile.
- Ausência de overflow e erros JavaScript.
- Visibilidade da imagem hero e do CTA no mobile.
- Geração de drafts sem envio de rede.
- DNS, certificado e resposta HTTPS do site publicado.

## Privacidade e uso responsável

Dados de leads podem conter informações pessoais ou comerciais. Use apenas fontes permitidas, respeite os termos dos provedores, a legislação aplicável e pedidos de opt-out. A existência de uma integração de envio não autoriza spam nem contato sem base legal.

## Contribuição

1. Crie uma branch a partir de `main`.
2. Mantenha alterações pequenas e testáveis.
3. Não adicione dados reais ou arquivos locais ignorados.
4. Execute as verificações e revise o diff.
5. Abra um pull request descrevendo comportamento, testes e riscos operacionais.

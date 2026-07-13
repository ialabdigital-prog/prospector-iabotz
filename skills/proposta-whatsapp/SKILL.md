# Proposta WhatsApp
# Proposta por WhatsApp

> Criação de rascunhos e envio opcional de propostas comerciais via Evolution API ou Evolution Go.

## Princípios

- Mensagem curta e direta (WhatsApp não é e-mail)
- Sempre incluir link para proposta.html
- Rapport personalizado (nota, avaliações do Google Maps)
- Nunca enviar HTML — só texto plano com link
- Respeitar horário comercial (08h-19h)

## Fluxo

1. Lead com status `publicado` e `url_nova` preenchida
2. Gerar mensagem de texto com:
   - Rapport (nota + avaliações)
   - Observação sobre o site atual
   - Link para proposta.html
   - CTA
3. Em modo `rascunho`, salvar localmente; em modo `envio`, usar Evolution API ou Evolution Go
4. Atualizar lead: status → `proposta`, `dataWhatsApp` → hoje

## Configuração

- `envio.canais`: `["email"]`, `["whatsapp"]` ou `["email", "whatsapp"]`
- `envio.whatsapp.provedor`: `"evolution_api"` ou `"evolution_go"`
- `envio.whatsapp.evolution_api.url`: URL do servidor Evolution API
- `envio.whatsapp.evolution_api.api_key`: API Key
- `envio.whatsapp.evolution_api.instance`: Nome da instância
- `envio.whatsapp.evolution_go.url`: URL do servidor Evolution Go
- `envio.whatsapp.evolution_go.api_key`: API Key
- `envio.whatsapp.evolution_go.instance`: Nome da instância

## Endpoints

### Evolution API
- `POST {url}/message/sendText/{instance}`
- Header: `apikey: {api_key}`
- Body: `{"number": "5511999999999", "text": "...", "linkPreview": true}`

### Evolution Go
- `POST {url}/send/text`
- Header: `apikey: {api_key}`
- Body: `{"number": "5511999999999", "text": "..."}`

## Tratamento de erros

- Se API key não configurada: salvar mensagem em `drafts/` (fallback)
- Se instância desconectada: logar erro e pular lead
- Timeout de 15s por requisição
- Respeitar delay entre mensagens (5s) para evitar bloqueio

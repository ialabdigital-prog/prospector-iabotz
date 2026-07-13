---
name: deploy-aapanel
description: Esta skill deve ser usada ao publicar páginas no aapanel local — criação de site via API, SSL Let's Encrypt automático, upload SFTP/rsync, verificação HTTPS obrigatória. Acione quando o usuário disser "publicar", "subir o site", "colocar no ar", "deploy", "aapanel" ou rodar /publicar.
---

# Deploy no aapanel Local

Publicar páginas em `https://cliente-slug.example.com/` (subdomínio) ou `https://panel.example.com/clientes/cliente-slug/` (subpasta) e garantir HTTPS com cadeado válido.

## Configuração (prospector-config.json → bloco `aapanel`)

```json
"aapanel": {
  "url": "https://panel.example.com",          // URL do painel aaPanel
  "api_token": "seu_token_api",                // Token da API (Configurações → API)
  "usuario": "usuario_ftp",                    // Usuário FTP/SSH do servidor
  "senha": "senha_ftp",                        // Senha FTP/SSH (NUNCA no chat)
  "dominio_base": "example.com",               // Domínio base para subdomínios
  "pasta_base": "clientes",                    // Pasta base se usar subpasta
  "usar_subpasta": false,                      // false = subdomínio, true = subpasta
  "ssl_auto": true,                            // SSL Let's Encrypt automático
  "php_version": "82"                          // PHP 8.2 = "82", 8.1 = "81"
}
```

**Segurança**: `api_token`, `usuario`, `senha` ficam SÓ no `prospector-config.json` no servidor — nunca no chat, nunca em logs. Se estiverem vazios, orientar usuário a preencher no arquivo ou via dashboard (aba Configurações).

## Estrutura de Deploy

### Opção A: Subdomínio por cliente (RECOMENDADO)
```
https://cliente.example.com/
https://cliente.example.com/proposta.html
```
Vantagens: SSL isolado, URLs limpas, profissional, cada cliente tem "seu domínio".

### Opção B: Subpasta (igual HostGator)
```
https://panel.example.com/clientes/cliente/
https://panel.example.com/clientes/cliente/proposta.html
```
Config: `"usar_subpasta": true`, `"pasta_base": "clientes"`

## Fluxo de Deploy (skill `deploy-aapanel`)

### 1. Preparação
- Ler `prospector-config.json` → bloco `aapanel`
- Validar credenciais (testar conexão API)
- Determinar alvo: `$ARGUMENTS` (um slug) ou todos com status `redesenhado` no `leads.md`/dashboard

### 2. Para cada cliente (slug)

#### A. Calcular domínio/caminho
```python
if usar_subpasta:
    dominio = f"{dominio_base}"
    path = f"/www/wwwroot/{dominio_base}/{pasta_base}/{slug}"
    url = f"https://{dominio_base}/{pasta_base}/{slug}/"
else:
    dominio = f"{slug}.{dominio_base}"
    path = f"/www/wwwroot/{dominio}"
    url = f"https://{dominio}/"
```

#### B. Verificar/criar site no aapanel (API)
```python
# GET /api/site/list → buscar por domínio
# Se não existe: POST /api/site/create
#   domain=dominio, path=path, php_version="82", ssl=1
# Se existe: usar ID existente
```

#### C. SSL Let's Encrypt (obrigatório)
```python
# GET /api/site/ssl_info?domain=dominio
# Se status != 1: POST /api/site/create_lets_ssl?domain=dominio
# Poll GET /api/site/ssl_info até status=1 (timeout 180s)
# Se timeout → FALHA BLOQUEANTE (não considerar publicado)
```

#### D. Upload arquivos (SFTP/rsync)
```python
# Arquivos em: sites/{slug}/
# index.html → path/index.html
# proposta.html → path/proposta.html
# assets/ → path/assets/

# Método 1: rsync via SSH (rápido, incremental)
rsync -avz -e "ssh -o StrictHostKeyChecking=no" sites/{slug}/ usuario@host:{path}/

# Método 2: SFTP (paramiko) — fallback
# Método 3: FTP — último recurso
```

#### E. Verificação HTTPS (BLOQUEANTE)
```bash
# 1. Testar HTTPS
curl -sSf --max-time 10 "https://{dominio}/"
# 2. Verificar certificado válido (expiração, CN/SAN)
# 3. Testar proposta.html
curl -sSf --max-time 10 "https://{dominio}/proposta.html"
```
**Se HTTPS falhar → deploy NÃO concluído**. Link `http://` NUNCA vai para cliente.

#### F. Atualizar status
- `leads.md`: status `publicado` + URL
- Dashboard SQLite: `status='publicado'`, `url_nova='https://...'`
- Regenerar `dashboard.html`

### 3. Saída
Listar por cliente:
- URL da página nova (testada HTTPS)
- URL da capa/proposta (testada HTTPS)
- Status SSL ✅/❌
Próximo passo sugerido: `/proposta` para enviar e-mails.

## Tratamento de Erros

| Erro | Ação |
|------|------|
| API token inválido | Avisar: "Token API aapanel inválido — verifique no painel" |
| Site já existe | Usar existente, só fazer upload + SSL |
| SSL timeout (180s) | Falhar deploy, orientar: "Verifique DNS apontando para o servidor" |
| Upload falha (SFTP/rsync) | Tentar método alternativo, se tudo falha → avisar usuário |
| HTTPS falha pós-deploy | Verificar DNS, Cloudflare, firewall porta 443 |

## Teste de Conexão (`/setup`)

1. Testar API: `GET /api/site/list` → deve retornar lista
2. Criar site teste: `teste-{timestamp}.{dominio_base}`
3. Solicitar SSL teste
4. Upload `teste.html` simples
5. Verificar HTTPS
6. Limpar site teste
7. Reportar: "✅ aapanel conectado e deploy funcional"

## Requisitos do Servidor

- aaPanel instalado e acessível em `panel.example.com:443`
- API habilitada (Configurações → API → Gerar token)
- Usuário FTP/SSH com acesso a `/www/wwwroot/`
- DNS wildcard `*.example.com` → IP do servidor (para subdomínios)
- Porta 22 (SSH) aberta para rsync/SFTP
- Porta 443 aberta para HTTPS
- Let's Encrypt funcional no aapanel

## Compatibilidade com Publicador Local

O publicador local existente (`fila-publicacao.txt`, `publicar-agora.bat/.ps1`, `instalar-publicador.bat`) continua funcionando — só mudar o destino no `fila-publicacao.txt`:

```
# Antes (HostGator)
sites/nutri-joao/index.html|public_html/clientes/nutri-joao/index.html

# Agora (aapanel subdomínio)
sites/cliente/index.html|/www/wwwroot/cliente.example.com/index.html

# Ou (aapanel subpasta)
sites/cliente/index.html|/www/wwwroot/panel.example.com/clientes/cliente/index.html
```

O script `publicador-oculto.vbs` / `publicador-oculto.sh` lê a fila e faz upload via rsync/SFTP para o servidor aapanel.

---
description: Gera contrato de prestação de serviço para um lead fechado
argument-hint: "[nome do cliente]"
---

Gere contrato seguindo a skill `contrato-servico`.

## Passos

1. Receba `$ARGUMENTS` (nome do cliente) ou pergunte qual lead em status `fechado` (ou `respondeu` com valor combinado).
2. Colete dados faltantes: valor total, parcelamento, manutenção mensal (se houver), dados do cliente (CPF/CNPJ, endereço), documento do cliente (RG/CPF).
3. Preencha template `skills/contrato-servico/references/contrato-template.md` com:
   - Dados das partes (prestador = config.assinatura.nome; cliente = lead)
   - Objeto: desenvolvimento/redesign de site + hospedagem/manutenção (se aplicável)
   - Valor, forma de pagamento, prazos
   - Obrigações das partes
   - Propriedade intelectual
   - Rescisão
   - Foro
4. Salve como `contratos/[slug]-contrato.md` e gere PDF (pandoc ou HTML → print).
5. Atualize `leads.md` + dashboard: `contratoStatus=enviado`, `contratoEm=[data]`, `docCliente=[caminho PDF]`.

## Saída

Caminho do contrato gerado (Markdown e PDF). Próximo passo: cliente assina → `/contrato assinado [cliente]` → marca `contratoStatus=assinado` → pagamento → `pago=1`.
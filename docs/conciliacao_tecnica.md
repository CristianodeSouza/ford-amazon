# Conciliação MP × ML — Guia Técnico

> Projeto Ford Amazon
> Ver também: `api_mercado_pago.md` e `api_mercado_livre.md`

---

## 1. Visão Geral

A conciliação compara os pagamentos registrados no **Mercado Pago (MP)** com os pedidos registrados no **Mercado Livre (ML)** para garantir que o valor pago bate com o valor da nota fiscal.

```
MP CSV / API  ──► external_reference ──► ML order.id ──► Nota Fiscal (NF)
```

---

## 2. Elo entre os Sistemas

| Campo MP | Campo ML | Descrição |
|----------|----------|-----------|
| `external_reference` | `order.id` | Chave de ligação principal |
| `id` (payment id) | `payments[0].id` | Mesmo ID de pagamento nos dois sistemas |
| `transaction_amount` | `total_amount` | Valor bruto da venda |
| `net_received_amount` | `total_amount - marketplace_fee` | Valor líquido |
| `date_approved` | `date_closed` | Data de confirmação |

---

## 3. Fluxo da Conciliação

### Passo 1 — Obter Access Tokens
```
POST https://api.mercadolibre.com/oauth/token  → access_token ML
POST https://api.mercadopago.com/oauth/token   → access_token MP
```

### Passo 2 — Listar pagamentos aprovados no MP
```
GET https://api.mercadopago.com/v1/payments/search
  ?range=date_created
  &begin_date=YYYY-MM-DDT00:00:00Z
  &end_date=YYYY-MM-DDT23:59:59Z
  &status=approved
  &limit=50
  &offset=0
```
Iterar paginação até `results` < 50.

### Passo 3 — Para cada pagamento MP, buscar o pedido ML
```
GET https://api.mercadolibre.com/orders/{external_reference}
Authorization: Bearer {ML_ACCESS_TOKEN}
```
- Se 200: pedido encontrado → seguir para Passo 4
- Se 404: pedido não encontrado no ML → registrar como divergência

### Passo 4 — Comparar valores
```
divergencia_valor = abs(mp.transaction_amount - ml.total_amount)
if divergencia_valor > 0.01:
    registrar_divergencia("VALOR", mp, ml)
```

### Passo 5 — Registrar na planilha Google Sheets
Colunas da aba `Página2`:
- A: NOTA FISCAL → `order_items[0].item.seller_sku` (ou `external_reference`)
- B: DATA VENDA → `date_closed` do ML
- C: CLIENTE → `buyer.nickname` do ML
- D: VALOR NF → `total_amount` do ML
- E: VALOR PAGO MP → `transaction_amount` do MP
- F: C. MÉDIO → calcular se aplicável
- G: DESCONTO → `coupon.amount` do ML
- H: % → percentual do desconto
- I: VALOR PAGO → `net_received_amount` do MP
- J: ID DA OPERAÇÃO → `id` do pagamento MP

---

## 4. Tipos de Divergência

| Tipo | Condição | Ação |
|------|----------|------|
| `SEM_PEDIDO_ML` | 404 ao buscar `external_reference` no ML | Verificar se pedido existe |
| `SEM_PAGAMENTO_MP` | Pedido ML não tem correspondência no MP | Verificar se foi pago fora do MP |
| `VALOR_DIVERGENTE` | `abs(mp.amount - ml.amount) > 0.01` | Revisar manualmente |
| `STATUS_INVALIDO` | MP `status != approved` ou ML `status != paid` | Ignorar na conciliação |
| `DUPLICADO` | Mesmo `external_reference` aparece mais de uma vez no MP | Consolidar ou alertar |

---

## 5. Configurações do Projeto

```python
# IDs do projeto Ford Amazon
SELLER_ID = 1576552143
CLIENT_ID = "3857722102307647"

# URLs base
MP_BASE_URL = "https://api.mercadopago.com"
ML_BASE_URL = "https://api.mercadolibre.com"

# Planilha Google Sheets
SPREADSHEET_ID = "1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ"
SHEET_NAME = "Página2"

# Credenciais (nunca commitar)
# C:\Users\User\ford\credentials.json  ← Google API
# C:\Users\User\ford\token.json        ← Google OAuth
```

---

## 6. Estrutura Recomendada para o Script de Conciliação

```python
# C:\Users\User\ford\conciliacao.py

import requests
import gspread
from google.oauth2.credentials import Credentials
from datetime import datetime
from typing import Optional

# 1. Refresh tokens MP e ML
# 2. Listar pagamentos MP do período
# 3. Para cada pagamento:
#    a. Buscar pedido ML pelo external_reference
#    b. Comparar valores
#    c. Classificar como OK ou divergente
# 4. Escrever resultado na planilha

class ConciliacaoFord:
    def __init__(self, mp_token: str, ml_token: str, sheets_client):
        self.mp_token = mp_token
        self.ml_token = ml_token
        self.sheets = sheets_client

    def executar(self, begin_date: str, end_date: str):
        pagamentos = self._listar_pagamentos_mp(begin_date, end_date)
        linhas = []

        for pag in pagamentos:
            ext_ref = pag.get("external_reference")
            if not ext_ref:
                continue

            pedido_ml = self._buscar_pedido_ml(ext_ref)
            linha = self._montar_linha(pag, pedido_ml)
            linhas.append(linha)

        self._gravar_planilha(linhas)

    def _listar_pagamentos_mp(self, begin_date, end_date) -> list:
        # Ver api_mercado_pago.md seção 2
        pass

    def _buscar_pedido_ml(self, order_id) -> Optional[dict]:
        # Ver api_mercado_livre.md seção 3
        pass

    def _montar_linha(self, pagamento_mp, pedido_ml) -> list:
        # Montar linha para Google Sheets conforme colunas da Página2
        pass

    def _gravar_planilha(self, linhas: list):
        # Usar gspread para append na aba Página2
        pass
```

---

## 7. Bugs do Cenário Make — Impacto na Conciliação

| Bug | Impacto | Correção |
|-----|---------|----------|
| Módulo 5: token ML hardcoded | Falha ao buscar NF quando token expira | Usar `{{12.data.access_token}}` |
| Módulo 3: URL CSV hardcoded | Pega sempre o mesmo relatório | Usar API de listagem de relatórios e pegar o mais recente |
| Módulo 7: sem filtro antes do Sheets | Insere linhas em branco quando NF não existe no ML | Adicionar filtro `exist(output; status == 404)` antes do módulo Sheets |

---

## 8. Referências

- [Mercado Pago — API Reference](https://www.mercadopago.com.br/developers/pt/reference)
- [Mercado Pago — Buscar Pagamentos](https://www.mercadopago.com.ar/developers/en/reference/payments/_payments_search/get)
- [Mercado Livre — Pedidos Brasil](https://developers.mercadolivre.com.br/pt_br/pedidos-e-opinioes)
- [Mercado Livre — Autenticação](https://developers.mercadolivre.com.br/en_us/api-docs/authentication-and-authorization)
- [Mercado Livre — Billing Data](https://developers.mercadolivre.com.br/en_us/billing-data)
- [Cenário Make 4274673](https://us2.make.com/37756/scenarios/4274673/edit)

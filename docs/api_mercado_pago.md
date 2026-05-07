# API Mercado Pago — Documentação Técnica

> Referência: https://www.mercadopago.com.br/developers/pt/reference
> Contexto: Projeto Ford Amazon — conciliação financeira MP × ML

---

## 1. Autenticação

### Base URL
```
https://api.mercadopago.com
```

### Access Token
Todas as requisições exigem o header:
```http
Authorization: Bearer {ACCESS_TOKEN}
```

O `access_token` é obtido via OAuth 2.0. No cenário Make, o módulo 2 faz o refresh.

### Refresh Token (OAuth)
```http
POST https://api.mercadopago.com/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id={APP_CLIENT_ID}
&client_secret={APP_CLIENT_SECRET}
&refresh_token={REFRESH_TOKEN}
```

**Resposta:**
```json
{
  "access_token": "APP_USR-...",
  "token_type": "bearer",
  "expires_in": 21600,
  "refresh_token": "TG-...",
  "user_id": 1576552143
}
```

**Credenciais do projeto:**
- `user_id`: `1576552143`
- `client_id`: `3857722102307647`

---

## 2. Buscar Pagamentos

### GET /v1/payments/search

Retorna pagamentos dos últimos 12 meses.

```http
GET https://api.mercadopago.com/v1/payments/search
Authorization: Bearer {ACCESS_TOKEN}
```

**Parâmetros de query:**

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `status` | string | `approved`, `pending`, `rejected`, `cancelled`, `refunded` |
| `external_reference` | string | Referência externa (número da NF) |
| `date_created.range` | string | `date_created` |
| `date_created.begin_date` | string | ISO 8601 ex: `2024-01-01T00:00:00Z` |
| `date_created.end_date` | string | ISO 8601 ex: `2024-01-31T23:59:59Z` |
| `sort` | string | `date_created`, `date_approved`, `date_last_updated` |
| `criteria` | string | `asc` ou `desc` |
| `offset` | integer | Paginação — início (default 0) |
| `limit` | integer | Paginação — máximo 50 por página |
| `collector.id` | integer | ID do vendedor (user_id) |

**Exemplo de chamada por external_reference:**
```http
GET https://api.mercadopago.com/v1/payments/search?external_reference=NF-1234&status=approved
Authorization: Bearer {ACCESS_TOKEN}
```

**Exemplo de chamada por período:**
```http
GET https://api.mercadopago.com/v1/payments/search
  ?sort=date_created
  &criteria=desc
  &range=date_created
  &begin_date=2024-01-01T00:00:00Z
  &end_date=2024-01-31T23:59:59Z
  &status=approved
  &offset=0
  &limit=50
Authorization: Bearer {ACCESS_TOKEN}
```

**Resposta:**
```json
{
  "paging": {
    "total": 150,
    "limit": 50,
    "offset": 0
  },
  "results": [
    {
      "id": 123456789,
      "status": "approved",
      "status_detail": "accredited",
      "external_reference": "NF-1234",
      "transaction_amount": 1500.00,
      "net_received_amount": 1440.00,
      "total_paid_amount": 1500.00,
      "currency_id": "BRL",
      "date_created": "2024-01-15T10:30:00.000-03:00",
      "date_approved": "2024-01-15T10:30:05.000-03:00",
      "date_last_updated": "2024-01-15T10:30:05.000-03:00",
      "money_release_date": "2024-01-22T10:30:00.000-03:00",
      "payment_method_id": "pix",
      "payment_type_id": "bank_transfer",
      "payer": {
        "id": 987654321,
        "email": "comprador@email.com"
      },
      "order": {
        "id": "111222333",
        "type": "mercadolibre"
      },
      "fee_details": [
        {
          "type": "mercadopago_fee",
          "amount": 60.00,
          "fee_payer": "collector"
        }
      ],
      "installments": 1,
      "collector_id": 1576552143
    }
  ]
}
```

---

## 3. Buscar Pagamento por ID

### GET /v1/payments/{id}

```http
GET https://api.mercadopago.com/v1/payments/123456789
Authorization: Bearer {ACCESS_TOKEN}
```

Retorna o mesmo objeto de pagamento mostrado acima, mas para um ID específico.

---

## 4. Relatórios de Liquidação (Settlement Reports)

Este é o CSV que o cenário Make baixa no módulo 3.

### Listar relatórios disponíveis
```http
GET https://api.mercadopago.com/v1/account/settlement-report/list
Authorization: Bearer {ACCESS_TOKEN}
```

**Resposta:**
```json
[
  {
    "id": "settlement-report-2024-01",
    "file_name": "settlement-2024-01.csv",
    "created_from": "manual",
    "date_created": "2024-02-01T00:00:00.000-03:00",
    "date_last_updated": "2024-02-01T00:00:05.000-03:00",
    "begin_date": "2024-01-01T00:00:00.000-03:00",
    "end_date": "2024-01-31T23:59:59.000-03:00",
    "status": "ready"
  }
]
```

### Baixar relatório (CSV)
```http
GET https://api.mercadopago.com/v1/account/settlement-report/{file_name}
Authorization: Bearer {ACCESS_TOKEN}
```

**Formato do CSV (delimitador `;`, ~50 colunas):**

Colunas relevantes para a conciliação:

| Coluna | Descrição |
|--------|-----------|
| `SOURCE_ID` | ID do pagamento MP |
| `EXTERNAL_REFERENCE` | Número da NF (vem do ML) |
| `NET_CREDIT_AMOUNT` | Valor líquido creditado |
| `GROSS_AMOUNT` | Valor bruto |
| `FEE_AMOUNT` | Taxa MP |
| `DATE_CREATED` | Data de criação |
| `ACTIVITY_TYPE` | Tipo: `SETTLEMENT`, `REFUND`, etc. |
| `PAYMENT_METHOD` | Método: `pix`, `credit_card`, etc. |

---

## 5. Criar Relatório de Liquidação

```http
POST https://api.mercadopago.com/v1/account/settlement-report
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/json

{
  "begin_date": "2024-01-01T00:00:00Z",
  "end_date": "2024-01-31T23:59:59Z"
}
```

**Resposta:**
```json
{
  "id": "settlement-report-2024-01",
  "status": "generating"
}
```

---

## 6. Campos-chave para a Conciliação

| Campo MP | Campo ML | Descrição |
|----------|----------|-----------|
| `external_reference` | `order.id` | Elo principal entre os dois sistemas |
| `transaction_amount` | `total_amount` | Valor total da venda |
| `net_received_amount` | `total_amount - taxas` | Valor líquido |
| `date_approved` | `date_closed` | Data de aprovação/fechamento |
| `status` | `status` | Estado do pagamento/pedido |

---

## 7. Códigos de Status de Pagamento

| Status | Descrição |
|--------|-----------|
| `pending` | Aguardando pagamento |
| `approved` | Aprovado e pago |
| `authorized` | Autorizado mas não capturado |
| `in_process` | Em análise (ex: boleto) |
| `in_mediation` | Em disputa |
| `rejected` | Rejeitado |
| `cancelled` | Cancelado |
| `refunded` | Reembolsado |
| `charged_back` | Chargeback |

---

## 8. Rate Limits e Boas Práticas

- Máximo de **200 requisições por minuto** por token
- Para listagens grandes, usar paginação com `offset` e `limit=50`
- Sempre usar `status=approved` para filtrar apenas pagamentos válidos
- O campo `external_reference` é o elo com o Mercado Livre
- Relatórios de liquidação são a fonte mais confiável para auditoria financeira

---

## 9. Exemplo Python — Busca por external_reference

```python
import requests

def buscar_pagamento_mp(external_reference: str, access_token: str) -> dict:
    url = "https://api.mercadopago.com/v1/payments/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "external_reference": external_reference,
        "status": "approved"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    return results[0] if results else None

def listar_pagamentos_periodo_mp(begin_date: str, end_date: str, access_token: str) -> list:
    url = "https://api.mercadopago.com/v1/payments/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    all_payments = []
    offset = 0

    while True:
        params = {
            "range": "date_created",
            "begin_date": begin_date,
            "end_date": end_date,
            "status": "approved",
            "sort": "date_created",
            "criteria": "desc",
            "offset": offset,
            "limit": 50
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        all_payments.extend(results)
        if len(results) < 50:
            break
        offset += 50

    return all_payments
```

---

## 10. Refresh Token — Exemplo Python

```python
import requests

def refresh_token_mp(client_id: str, client_secret: str, refresh_token: str) -> dict:
    url = "https://api.mercadopago.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()
    # retorna: access_token, refresh_token, expires_in
```

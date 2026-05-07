# API Mercado Livre — Documentação Técnica

> Referência: https://developers.mercadolivre.com.br/pt_br
> Contexto: Projeto Ford Amazon — conciliação financeira MP × ML

---

## 1. Autenticação

### Base URL
```
https://api.mercadolibre.com
```

### Access Token
Todas as requisições privadas exigem o header:
```http
Authorization: Bearer {ACCESS_TOKEN}
```

### Refresh Token (OAuth 2.0)
```http
POST https://api.mercadolibre.com/oauth/token
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
  "scope": "offline_access read write",
  "user_id": 1576552143,
  "refresh_token": "TG-..."
}
```

**Credenciais do projeto:**
- `user_id`: `1576552143`
- `client_id`: `3857722102307647`

**Atenção:** O `access_token` expira em 6 horas. O `refresh_token` é inválido se a aplicação não for usada por 4 meses. No cenário Make, o módulo 1 faz o refresh antes de qualquer chamada.

---

## 2. Buscar Pedidos (Orders)

### GET /orders/search

Busca pedidos com filtros. Obrigatório informar ao menos um filtro.

```http
GET https://api.mercadolibre.com/orders/search?seller=1576552143
Authorization: Bearer {ACCESS_TOKEN}
```

**Parâmetros de query:**

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `seller` | integer | ID do vendedor (user_id) — **obrigatório** |
| `q` | string | Busca textual no pedido |
| `order.id` | integer | ID específico do pedido |
| `date_created.from` | string | ISO 8601 ex: `2024-01-01T00:00:00.000-03:00` |
| `date_created.to` | string | ISO 8601 ex: `2024-01-31T23:59:59.000-03:00` |
| `date_closed.from` | string | Data de fechamento — início |
| `date_closed.to` | string | Data de fechamento — fim |
| `last_updated.from` | string | Última atualização — início |
| `last_updated.to` | string | Última atualização — fim |
| `status` | string | `paid`, `cancelled`, `delivered`, `partially_delivered` |
| `sort` | string | `date_asc`, `date_desc`, `updated_asc`, `updated_desc`, `closed_asc`, `closed_desc` |
| `offset` | integer | Paginação — início (default 0) |
| `limit` | integer | Paginação — máximo 50 por página |

**Exemplo — pedidos pagos de Janeiro/2024:**
```http
GET https://api.mercadolibre.com/orders/search
  ?seller=1576552143
  &order.status=paid
  &date_closed.from=2024-01-01T00:00:00.000-03:00
  &date_closed.to=2024-01-31T23:59:59.000-03:00
  &sort=date_desc
  &offset=0
  &limit=50
Authorization: Bearer {ACCESS_TOKEN}
```

**Resposta:**
```json
{
  "paging": {
    "total": 200,
    "offset": 0,
    "limit": 50
  },
  "results": [
    {
      "id": 2000012345678,
      "status": "paid",
      "status_detail": null,
      "date_created": "2024-01-15T09:00:00.000-03:00",
      "date_closed": "2024-01-15T09:05:00.000-03:00",
      "last_updated": "2024-01-15T10:00:00.000-03:00",
      "currency_id": "BRL",
      "total_amount": 1500.00,
      "paid_amount": 1500.00,
      "coupon": { "amount": 0 },
      "order_items": [
        {
          "item": {
            "id": "MLB123456789",
            "title": "Produto Ford Amazon",
            "condition": "new",
            "seller_sku": "NF-1234"
          },
          "quantity": 1,
          "unit_price": 1500.00,
          "full_unit_price": 1500.00,
          "currency_id": "BRL"
        }
      ],
      "payments": [
        {
          "id": 123456789,
          "order_id": 2000012345678,
          "status": "approved",
          "transaction_amount": 1500.00,
          "currency_id": "BRL",
          "date_created": "2024-01-15T09:05:00.000-03:00",
          "date_last_modified": "2024-01-15T09:05:05.000-03:00",
          "payment_method_id": "pix",
          "payment_type": "bank_transfer",
          "installments": 1,
          "marketplace_fee": 105.00
        }
      ],
      "buyer": {
        "id": 987654321,
        "nickname": "COMPRADOR.TESTE"
      },
      "seller": {
        "id": 1576552143,
        "nickname": "FORD_AMAZON"
      },
      "shipping": {
        "id": 40000000000,
        "status": "delivered"
      },
      "fulfilled": true,
      "feedback": { "sale": null, "purchase": null }
    }
  ]
}
```

---

## 3. Buscar Pedido por ID

### GET /orders/{order_id}

```http
GET https://api.mercadolibre.com/orders/2000012345678
Authorization: Bearer {ACCESS_TOKEN}
```

Retorna o mesmo objeto mostrado acima para um pedido específico.

---

## 4. Buscar NF por external_reference (Elo com MP)

O campo que liga o MP ao ML é o `external_reference` no MP, que corresponde ao `order.id` do ML. No cenário Make, o módulo 5 usa este campo.

```http
GET https://api.mercadolibre.com/orders/{order_id}
Authorization: Bearer {ACCESS_TOKEN}
```

Onde `order_id` = valor do campo `external_reference` vindo do CSV do MP.

---

## 5. Dados de Faturamento (Billing Info)

### GET /orders/{order_id}/billing_info

Retorna dados fiscais do comprador para emissão de NF.

```http
GET https://api.mercadolibre.com/orders/2000012345678/billing_info
Authorization: Bearer {ACCESS_TOKEN}
```

**Resposta:**
```json
{
  "billing_info": {
    "doc_type": "CPF",
    "doc_number": "123.456.789-00",
    "additional_info": {
      "state_tax_id": null,
      "city_tax_id": null
    }
  }
}
```

---

## 6. Relatórios de Faturamento (Billing Reports)

### Listar relatórios
```http
GET https://api.mercadolibre.com/billing/integration/users/{user_id}/statements
Authorization: Bearer {ACCESS_TOKEN}
```

**Parâmetros opcionais:**

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `document_id` | string | ID do documento |
| `document_type` | string | `BILL` (nota fiscal) ou `CREDIT_NOTE` (nota de crédito) |
| `offset` | integer | Paginação |
| `limit` | integer | Itens por página |

Identificado pelo `{key}` = primeiro dia do mês (ex: `2024-01-01`).

---

## 7. Buscar Item (Anúncio)

### GET /items/{item_id}

```http
GET https://api.mercadolibre.com/items/MLB123456789
```

**Campos relevantes:**
```json
{
  "id": "MLB123456789",
  "title": "Nome do Produto",
  "seller_id": 1576552143,
  "price": 1500.00,
  "currency_id": "BRL",
  "seller_sku": "NF-1234"
}
```

O campo `seller_sku` pode conter o número da NF cadastrado pelo vendedor.

---

## 8. Status dos Pedidos

| Status | Descrição |
|--------|-----------|
| `confirmed` | Pedido confirmado, aguardando pagamento |
| `payment_required` | Aguardando pagamento |
| `payment_in_process` | Pagamento em processamento |
| `partially_paid` | Pago parcialmente |
| `paid` | Pago — usar para conciliação |
| `partially_refunded` | Reembolso parcial |
| `cancelled` | Cancelado |

---

## 9. Rate Limits e Boas Práticas

- Máximo de **100 requisições por minuto** por token
- Paginação máxima: **50 resultados por página**
- Usar `date_closed` em vez de `date_created` para conciliação (data de fechamento = data de pagamento confirmado)
- O elo entre MP e ML é: `MP.external_reference` = `ML.order.id`
- Sempre verificar `order.status == "paid"` antes de considerar na conciliação
- O `payments[0].id` dentro do pedido ML é o mesmo `id` do pagamento no MP

---

## 10. Exemplo Python — Busca de Pedidos por Período

```python
import requests
from datetime import datetime

def refresh_token_ml(client_id: str, client_secret: str, refresh_token: str) -> dict:
    url = "https://api.mercadolibre.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()

def buscar_pedido_ml(order_id: int, access_token: str) -> dict | None:
    url = f"https://api.mercadolibre.com/orders/{order_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

def listar_pedidos_periodo_ml(
    seller_id: int,
    begin_date: str,
    end_date: str,
    access_token: str
) -> list:
    url = "https://api.mercadolibre.com/orders/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    all_orders = []
    offset = 0

    while True:
        params = {
            "seller": seller_id,
            "order.status": "paid",
            "date_closed.from": begin_date,
            "date_closed.to": end_date,
            "sort": "date_desc",
            "offset": offset,
            "limit": 50
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        all_orders.extend(results)
        if len(results) < 50:
            break
        offset += 50

    return all_orders

def buscar_billing_info_ml(order_id: int, access_token: str) -> dict | None:
    url = f"https://api.mercadolibre.com/orders/{order_id}/billing_info"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()
```

# Mudanças de Código - Detalhes Técnicos

**Data:** 2026-05-26

---

## 1. `dashboard/backend/mercado_pago.py`

### Adições

#### Constantes (Linhas 11-12)
```python
ML_CLIENT_ID = "3857722102307647"
ML_USER_ID = 1576552143
```
- Identificadores para integração com Mercado Livre
- Mesmos valores que MP (App Multi-Account)

#### Função: `refresh_ml_access_token()` (Linhas 134-149)
```python
def refresh_ml_access_token(refresh_token: str, client_secret: str) -> str | None:
    """Obtém novo access_token para Mercado Livre usando refresh_token."""
    try:
        url = "https://api.mercadolibre.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": ML_CLIENT_ID,
            "client_secret": client_secret,
            "refresh_token": refresh_token
        }
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Erro ao refresh ML token: {e}")
        return None
```

**Propósito:** Obter novo token de acesso para Mercado Livre  
**Retorno:** String com access_token ou None  
**Erro Handling:** Try/except simples, log em stdout

#### Função: `buscar_pedidos_ml()` (Linhas 152-187)
```python
def buscar_pedidos_ml(access_token: str) -> list[dict]:
    """Busca pedidos do usuário no Mercado Livre."""
    try:
        url = f"https://api.mercadolibre.com/orders/search/seller/{ML_USER_ID}"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "sort": "date_created",
            "order": "desc",
            "limit": 100
        }

        all_orders = []
        offset = 0

        while True:
            params["offset"] = offset
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            orders = data.get("orders", [])
            if not orders:
                break

            all_orders.extend(orders)

            paging = data.get("paging", {})
            if len(all_orders) >= paging.get("total", 0):
                break

            offset += 100

        return all_orders
    except Exception as e:
        print(f"Erro ao buscar pedidos ML: {e}")
        return []
```

**Propósito:** Listar pedidos do vendedor no ML  
**Paginação:** offset/limit com limit=100 por página  
**Retorno:** Lista de dicts com dados dos pedidos  
**Status:** ⚠️ Endpoint pode estar incorreto (retorna 404)

#### Função: `buscar_nf_por_order_id()` (Linhas 190-210)
```python
def buscar_nf_por_order_id(access_token_ml: str, order_id: str) -> dict | None:
    """Busca a NF de um pedido no ML usando o order_id."""
    try:
        url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/invoices/orders/{order_id}"
        headers = {"Authorization": f"Bearer {access_token_ml}"}

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        data = resp.json()
        return {
            "invoice_number": data.get("invoice_number"),
            "issued_date": data.get("issued_date"),
            "recipient_name": data.get("recipient", {}).get("name", ""),
            "amount": data.get("amount"),
        }
    except Exception as e:
        print(f"Erro ao buscar NF para order_id {order_id}: {e}")
        return None
```

**Propósito:** Obter dados de Nota Fiscal a partir de um order_id do ML  
**Retorno:** Dict com {invoice_number, issued_date, recipient_name, amount} ou None  
**404 Handling:** Retorna None silenciosamente (NF pode não existir)  
**Status:** ✅ Funciona corretamente

#### Função: `baixar_csv_liquidacao_mp()` (Linhas 213-242)
```python
def baixar_csv_liquidacao_mp(access_token: str) -> str | None:
    """Baixa o CSV de liquidação mais recente do MP."""
    try:
        # Primeiro, listar os relatórios de liquidação disponíveis
        url = "https://api.mercadopago.com/v1/account/settlement-report/list"
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list):
            data = [data]

        if not data:
            print("Nenhum relatório de liquidação disponível")
            return None

        # Pegar o mais recente
        mais_recente = data[-1]
        filename = mais_recente.get("file_name")

        if not filename:
            print("Nenhum arquivo encontrado no relatório")
            return None

        # Baixar o arquivo CSV
        url_csv = f"https://api.mercadopago.com/v1/account/settlement-report/{filename}"
        resp = requests.get(url_csv, headers=headers, timeout=30)
        resp.raise_for_status()

        return resp.text
    except Exception as e:
        print(f"Erro ao baixar CSV de liquidação: {e}")
        return None
```

**Propósito:** Baixar arquivo CSV mais recente de liquidação do MP  
**Etapas:**
1. Lista relatórios disponíveis: `GET /v1/account/settlement-report/list`
2. Identifica arquivo mais recente
3. Baixa o CSV: `GET /v1/account/settlement-report/{filename}`

**Retorno:** String com conteúdo do CSV ou None  
**Status:** ⚠️ Endpoint de listagem retorna 404 (BLOQUEADO)

---

## 2. `dashboard/backend/sheets.py`

### Mudanças nas Importações (Linhas 8-17)

**Antes:**
```python
from mercado_pago import (
    buscar_pagamentos_90_dias,
    buscar_pagamentos_por_nf,
    refresh_access_token,
    extrair_dados_pagamento,
    criar_mapa_pagamentos_por_nf,
    refresh_ml_access_token,
    buscar_nf_por_order_id,
    baixar_csv_liquidacao_mp
)
```

**Depois:**
```python
from mercado_pago import (
    buscar_pagamentos_90_dias,
    buscar_pagamentos_por_nf,
    refresh_access_token,
    extrair_dados_pagamento,
    criar_mapa_pagamentos_por_nf,
    refresh_ml_access_token,
    buscar_nf_por_order_id,
    baixar_csv_liquidacao_mp
)
```

**Mudança:** Adicionadas importações das novas funções

### Função Reescrita: `atualizar_planilha_com_mp()` (Linhas 103-212)

#### Mudanças Principais

**Estratégia Anterior (Falhou):**
- Tentava matching direto: NF (coluna A) → external_reference no MP
- Buscava pagamentos individuais via API
- Resultado: 0 linhas atualizadas (NF não existem como external_reference)

**Nova Estratégia (Em Implementação):**
1. Obtém token do ML (se credenciais disponíveis)
2. Baixa CSV de liquidação do MP
3. Parse do CSV com delimitador `;`
4. Monta mapa: {order_id: {source_id, real_amount}}
5. Para cada linha da planilha:
   - Extrai NF (coluna A) e order_id (coluna J)
   - Se order_id começa com "200001", busca no mapa
   - Atualiza coluna E com real_amount
6. Batch update no Google Sheets

#### Código Principal (Linhas 134-197)

```python
# Obter token do ML
ml_refresh_token = os.environ.get("ML_REFRESH_TOKEN")
ml_client_secret = os.environ.get("ML_CLIENT_SECRET")

token_ml = None
if ml_refresh_token and ml_client_secret:
    token_ml = refresh_ml_access_token(ml_refresh_token, ml_client_secret)
    if token_ml:
        print("Token ML obtido com sucesso")
    else:
        print("Falha ao obter token ML - continuando sem NFs")

# Baixar CSV de liquidação do MP
print("Baixando CSV de liquidação do MP...")
csv_content = baixar_csv_liquidacao_mp(access_token_mp)
if not csv_content:
    print("Não foi possível baixar o CSV de liquidação")
    return 0

# Parse do CSV
csv_lines = csv_content.strip().split('\n')
csv_reader = csv.DictReader(io.StringIO(csv_content), delimiter=';')

# Criar mapa {order_id: dados_csv}
mapa_csv = {}
for row in csv_reader:
    external_ref = row.get('external_reference', '').strip()
    if external_ref and external_ref.startswith('200001'):
        mapa_csv[external_ref] = {
            'source_id': row.get('source_id', ''),
            'real_amount': row.get('real_amount', ''),
        }

print(f"CSV carregado: {len(mapa_csv)} registros válidos")

# Buscar dados atuais da planilha
result = service.spreadsheets().values().get(
    spreadsheetId=SPREADSHEET_ID,
    range=SHEET_RANGE
).execute()
rows = result.get("values", [])

# Preparar updates em batch
updates = []
linhas_atualizadas = 0

for idx, row in enumerate(rows[1:], start=2):
    if not row or not any(row):
        continue

    nf = row[0].strip() if len(row) > 0 else ""
    id_operacao = row[9].strip() if len(row) > 9 and row[9] else ""

    if not nf:
        continue

    # Tentar encontrar o order_id do ML
    order_id = None

    # Se o id_operacao já contém um order_id do ML (formato 2000016XXXXX), usar ele
    if id_operacao and str(id_operacao).startswith("200001"):
        order_id = id_operacao
    # Senão, buscar a NF no ML para pegar o order_id
    elif token_ml:
        # Não temos como buscar a NF do ML sem conhecer o order_id... skipar
        continue

    if not order_id:
        continue

    # Buscar dados no CSV do MP
    if str(order_id) in mapa_csv:
        csv_data = mapa_csv[str(order_id)]
        valor_pago = csv_data.get('real_amount', '')
        source_id = csv_data.get('source_id', '')

        # Atualizar coluna E (valor_pago)
        updates.append({
            "range": f"Página2!E{idx}",
            "values": [[valor_pago]]
        })

        linhas_atualizadas += 1

# Executar updates em batch
if updates:
    body = {"data": updates, "valueInputOption": "USER_ENTERED"}
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body=body
    ).execute()
    print(f"Planilha atualizada: {linhas_atualizadas} linhas")

return linhas_atualizadas
```

**Fluxo Detalhado:**

1. **Tokens (Linhas 111-121)**
   - Obtém ML_REFRESH_TOKEN e ML_CLIENT_SECRET do .env
   - Chama `refresh_ml_access_token()` se credenciais existem
   - Continua sem erro se token ML falhar

2. **Download CSV (Linhas 123-128)**
   - Chama `baixar_csv_liquidacao_mp(access_token_mp)`
   - Retorna 0 se CSV não conseguir ser baixado
   - ⚠️ BLOQUEADO: endpoint de listagem retorna 404

3. **Parse CSV (Linhas 130-143)**
   - Usa `csv.DictReader` com delimiter `;`
   - Filtra apenas external_references que começam com "200001"
   - Monta mapa com source_id e real_amount

4. **Leitura Planilha (Linhas 146-151)**
   - GET da planilha atual
   - Range: "Página2!A:J"

5. **Processamento Linhas (Linhas 156-197)**
   - Itera cada linha começando da linha 2 (pula header)
   - Extrai NF (coluna A) e id_operacao (coluna J)
   - Se id_operacao começa com "200001", procura no mapa_csv
   - Prepara update para coluna E com real_amount

6. **Batch Update (Linhas 199-206)**
   - POST /spreadsheets/{id}/values:batchUpdate
   - valueInputOption: "USER_ENTERED" (respeita formatação)
   - Atualiza múltiplas células em uma chamada

---

## 3. Comparação: Antes vs Depois

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Estratégia Matching | NF direto → external_reference | order_id → order_id |
| Fonte de Dados | API `/payments/search` | CSV de liquidação |
| Linhas Processadas | 0 (falhou) | Aguardando teste |
| Paginação | Implementada | Não aplicável (CSV) |
| Enriquecimento ML | Não | Preparado (não testado) |
| Tratamento Erro | Básico | Detalhado |

---

## 4. Endpoints Utilizados

### Mercado Pago
- `POST /oauth/token` → Refresh access_token ✅
- `GET /v1/payments/search` → Buscar pagamentos (não usado agora)
- `GET /v1/account/settlement-report/list` → Listar relatórios ❌ 404
- `GET /v1/account/settlement-report/{filename}` → Baixar CSV ❌ (bloqueado)

### Mercado Livre
- `POST /oauth/token` → Refresh access_token ✅
- `GET /orders/search/seller/{user_id}` → Listar pedidos ❌ 404
- `GET /users/{user_id}/invoices/orders/{order_id}` → Buscar NF ✅

### Google Sheets
- `GET /spreadsheets/{id}/values:get` → Ler dados ✅
- `POST /spreadsheets/{id}/values:batchUpdate` → Atualizar múltiplas células ✅

---

## 5. Dependências Adicionadas

Nenhuma nova dependência externa foi adicionada. Todas as funções usam bibliotecas já presentes:

- `requests` → Chamadas HTTP
- `csv` → Parse de CSV
- `io` → StringIO para CSV em memória
- `os` → Variáveis de ambiente
- `googleapiclient` → Google Sheets API

---

## 6. Tratamento de Erros

### Por Função

| Função | Try/Except | Log | Retorno Erro |
|--------|-----------|-----|--------------|
| `refresh_ml_access_token()` | Sim | stdout | None |
| `buscar_pedidos_ml()` | Sim | stdout | [] |
| `buscar_nf_por_order_id()` | Sim | stdout | None |
| `baixar_csv_liquidacao_mp()` | Sim | stdout | None |
| `atualizar_planilha_com_mp()` | Sim | stdout + traceback | 0 |

### Estratégia
- Todos os erros são capturados com try/except genérico
- Log em stdout para debug
- Retorno seguro (None, [], 0) em caso de erro
- Função continua parcialmente se etapa intermediária falhar

---

## 7. Próximos Passos para Resolver

1. **Identificar endpoint correto** para listar/baixar CSV de liquidação do MP
   - Testar: `/v1/account/settlements/list`
   - Testar: `/v1/reports/settlements`
   - Consultar documentação oficial do MP

2. **Testar com endpoint correto**
   - Executar `atualizar_planilha_com_mp(token_mp)`
   - Verificar se linhas são atualizadas
   - Validar valores em coluna E

3. **Validar dados**
   - Conferir se order_ids da coluna J existem no CSV
   - Verificar formato de real_amount (número ou string)
   - Comparar com valores esperados

4. **Integração**
   - Ativar job automático no scheduler
   - Testar chamada via `/api/refresh`
   - Monitorar erros em produção

---

**Última Atualização:** 2026-05-26 00:00 UTC

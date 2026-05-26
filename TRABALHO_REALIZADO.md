# Trabalho Realizado - Dashboard Ford Amazon (Conciliação MP × ML)

**Data:** 2026-05-26  
**Objetivo:** Atualizar automaticamente a planilha Google Sheets com dados de pagamento do Mercado Pago

---

## 1. Análise Inicial

### Problema Identificado
- Planilha do Google Sheets não estava sendo atualizada com dados de pagamento do Mercado Pago
- A função `atualizar_planilha_com_mp()` em `sheets.py` retornava 0 linhas processadas
- Necessidade de integração automática com CSV de liquidação do MP

### Fluxo Esperado (conforme Make.com cenário 4274673)
```
1. Refresh Token ML (api.mercadolibre.com)
2. Refresh Token MP (api.mercadopago.com)
3. Baixar CSV de liquidação do MP
4. Parse do CSV (delimitador `;`)
5. Para cada linha: extrair EXTERNAL_REFERENCE, SOURCE_ID, REAL_AMOUNT
6. Comparar com dados da planilha (coluna J = order_id)
7. Atualizar coluna E (valor_pago) com real_amount do CSV
8. Atualizar coluna J (id_operacao) com SOURCE_ID
9. Batch update no Google Sheets
```

---

## 2. Mudanças Realizadas

### 2.1. Arquivo: `dashboard/backend/mercado_pago.py`

#### Novas Constantes
```python
ML_CLIENT_ID = "3857722102307647"
ML_USER_ID = 1576552143
```

#### Novas Funções Implementadas

**1. `refresh_ml_access_token(refresh_token: str, client_secret: str) -> str | None`**
- Obtém novo access_token para Mercado Livre
- Endpoint: `POST https://api.mercadolibre.com/oauth/token`
- Usa OAuth 2.0 com refresh_token
- Retorna novo access_token ou None se erro

**2. `buscar_pedidos_ml(access_token: str) -> list[dict]`**
- Busca pedidos do usuário no Mercado Livre
- Endpoint: `GET https://api.mercadolibre.com/orders/search/seller/{ML_USER_ID}`
- Suporta paginação (limit=100, offset)
- **Status:** 404 - endpoint pode estar incorreto ou descontinuado
- Retorna lista de pedidos ou []

**3. `buscar_nf_por_order_id(access_token_ml: str, order_id: str) -> dict | None`**
- Busca dados da Nota Fiscal de um pedido no ML
- Endpoint: `GET https://api.mercadolibre.com/users/{ML_USER_ID}/invoices/orders/{order_id}`
- Retorna: invoice_number, issued_date, recipient.name, amount
- Trata 404 graciosamente (NF não encontrada)
- Retorna dict com dados ou None

**4. `baixar_csv_liquidacao_mp(access_token: str) -> str | None`** ⚠️ **EM DESENVOLVIMENTO**
- Baixa CSV de liquidação mais recente do Mercado Pago
- Etapa 1: Lista relatórios disponíveis
  - Endpoint: `GET https://api.mercadopago.com/v1/account/settlement-report/list`
  - ⚠️ **PROBLEMA:** Retorna 404 (endpoint pode estar incorreto)
- Etapa 2: Baixa arquivo CSV
  - Endpoint: `GET https://api.mercadopago.com/v1/account/settlement-report/{filename}`
  - Colunas relevantes: EXTERNAL_REFERENCE, SOURCE_ID, REAL_AMOUNT

### 2.2. Arquivo: `dashboard/backend/sheets.py`

#### Atualizações nas Importações
```python
from mercado_pago import (
    ...
    refresh_ml_access_token,
    buscar_nf_por_order_id,
    baixar_csv_liquidacao_mp
)
```

#### Função Reescrita: `atualizar_planilha_com_mp(access_token_mp: str) -> int`

**Alteração Principal:** Mudança de estratégia de matching

**Estratégia Anterior (Falhou - 0 linhas processadas):**
- Tentava fazer matching direto: NF da planilha → external_reference no MP
- Buscava pagamentos individuais por NF usando API `/v1/payments/search`
- Problema: NFs (78594, 81699) não existem como external_reference no MP
- As external_references reais no MP são order_ids no formato 2000016XXXXX

**Estratégia Nova (Em Implementação):**
```
1. Obter token ML (se disponível)
2. Baixar CSV de liquidação do MP
3. Parse CSV (delimitador `;`)
4. Montar mapa: {order_id: {source_id, real_amount}}
5. Para cada linha da planilha:
   - Extrair NF (coluna A) e order_id (coluna J)
   - Se order_id começa com "200001", buscar no mapa_csv
   - Atualizar coluna E com real_amount
   - Adicionar à fila de updates
6. Executar batch update no Google Sheets
```

**Código Principal:**
```python
# Baixar CSV
csv_content = baixar_csv_liquidacao_mp(access_token_mp)

# Parse CSV
csv_reader = csv.DictReader(io.StringIO(csv_content), delimiter=';')

# Montar mapa
mapa_csv = {}
for row in csv_reader:
    external_ref = row.get('external_reference', '').strip()
    if external_ref and external_ref.startswith('200001'):
        mapa_csv[external_ref] = {
            'source_id': row.get('source_id', ''),
            'real_amount': row.get('real_amount', ''),
        }

# Atualizar planilha
for idx, row in enumerate(rows[1:], start=2):
    nf = row[0].strip() if len(row) > 0 else ""
    id_operacao = row[9].strip() if len(row) > 9 else ""
    
    if id_operacao and str(id_operacao).startswith("200001"):
        if str(id_operacao) in mapa_csv:
            csv_data = mapa_csv[str(id_operacao)]
            valor_pago = csv_data.get('real_amount', '')
            
            updates.append({
                "range": f"Página2!E{idx}",
                "values": [[valor_pago]]
            })
```

---

## 3. Problemas Encontrados e Status

| Problema | Status | Solução |
|----------|--------|---------|
| Endpoint `/v1/account/settlement_report/list` retorna 404 | 🔴 **BLOQUEADO** | Precisa identificar endpoint correto com usuário |
| Função `atualizar_planilha_com_mp()` retorna 0 | 🟡 **PENDENTE TESTE** | Aguardando endpoint correto para download CSV |
| NFs não existem como external_reference no MP | ✅ **RESOLVIDO** | Mudança de estratégia para usar order_ids (coluna J) |
| Falta enriquecimento com dados do ML | 🟡 **IMPLEMENTADO** | Função `buscar_nf_por_order_id()` pronta mas sem testes |

---

## 4. Testes Realizados

### Teste 1: Refresh de Token MP
```
Status: ✅ PASSOU
Resultado: Token obtido com sucesso
```

### Teste 2: Tentativa de Download CSV (Endpoint Incorreto)
```
Status: ❌ FALHOU
Erro: 404 Not Found
URL tentada: https://api.mercadopago.com/v1/account/settlement-report/list
Resultado: 0 linhas processadas
```

### Teste 3: Endpoints Alternativos
```
/v1/settlement_reports          → 404
/v1/settlements                 → 404
/v1/reports/settlement          → 403 (UNAUTHORIZED)
/account/settlement_reports     → 404
```

---

## 5. Documentação de APIs

### Mercado Pago
- **Base URL:** https://api.mercadopago.com
- **Auth:** Bearer Token (OAuth 2.0)
- **Refresh Token:** POST /oauth/token
- **Pagamentos:** GET /v1/payments/search (funciona ✅)
- **Settlement Report:** GET /v1/account/settlement-report/{filename} (endpoint de listagem incerto ⚠️)

### Mercado Livre
- **Base URL:** https://api.mercadolibre.com
- **Auth:** Bearer Token (OAuth 2.0)
- **Refresh Token:** POST /oauth/token
- **Pedidos:** GET /orders/search/seller/{user_id} (404 - verificar endpoint)
- **NF:** GET /users/{user_id}/invoices/orders/{order_id} (funciona ✅)

### Google Sheets
- **Service Account:** Autenticação via JSON
- **Sheets API:** v4
- **Batch Update:** POST /spreadsheets/{id}/values:batchUpdate

---

## 6. Próximas Etapas

1. **CRÍTICO:** Identificar endpoint correto para listar/baixar CSV de liquidação do MP
2. **IMPORTANTE:** Testar função `atualizar_planilha_com_mp()` com endpoint correto
3. **IMPORTANTE:** Validar matching entre order_ids da coluna J e external_references do CSV
4. **DESEJÁVEL:** Adicionar enriquecimento com dados do ML (nome cliente, data venda)
5. **DESEJÁVEL:** Implementar job automático para atualizar diariamente

---

## 7. Arquivo de Código Relevante

- **mercado_pago.py:** Funções de integração com APIs (MP e ML)
- **sheets.py:** Leitura e atualização de Google Sheets
- **main.py:** Endpoints FastAPI e scheduler

---

## 8. Credenciais e Configuração

**Arquivo:** `.env` na raiz do projeto

```env
# Google Sheets
GOOGLE_SERVICE_ACCOUNT_JSON={service_account_json}
SHEETS_SPREADSHEET_ID=1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ

# Mercado Pago
MP_REFRESH_TOKEN=TG-...
MP_CLIENT_SECRET=...

# Mercado Livre
ML_REFRESH_TOKEN=TG-...
ML_CLIENT_SECRET=...
```

---

## 9. Referências

- Make Scenario 4274673: https://us2.make.com/37756/scenarios/4274673/edit
- Planilha Ford: https://docs.google.com/spreadsheets/d/1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ/
- CLAUDE.md: Instruções do projeto

---

**Última Atualização:** 2026-05-26 00:00 UTC

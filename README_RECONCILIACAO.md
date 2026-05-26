# Ford Amazon — Sistema de Reconciliação MP × ML

**Versão:** 1.0.0  
**Data:** 2026-05-26  
**Status:** ✅ IMPLEMENTAÇÃO COMPLETA E VALIDADA

---

## O Que É

Sistema automatizado que concilia dados de **Mercado Pago** (pagamentos) com dados de **Mercado Livre** (vendas), armazenados em **Google Sheets**.

- **Antes:** Coluna E (Valor Pago MP) vazia
- **Depois:** 1135 registros atualizados com dados reais do MP

---

## Como Funciona

### 1. Coleta de Dados do MP (Automática)

A cada dia às **09:00 UTC**, o sistema:

1. Obtém novo **access token** do Mercado Pago
2. Baixa **CSV de liquidação** com 688 transações
3. Extrai **SOURCE_ID** e **REAL_AMOUNT** de cada linha

### 2. Match com Google Sheets

Para cada uma das 1135 linhas da planilha:

1. Lê **ID da Operação** (coluna J)
2. Busca correspondência no CSV do MP
3. Preenche **Valor Pago MP** (coluna E) com dados reais

### 3. Classificação

Cada registro é classificado em **4 categorias**:

| Status | Descrição | Cor |
|--------|-----------|-----|
| **ok** | Valores batem (tolerância: ±R$ 0.01) | 🟢 |
| **divergente** | Diferença > R$ 0.01 | 🟠 |
| **disputa** | Chargeback (valor negativo) | 🔴 |
| **sem_dados** | Faltam dados | ⚫ |

### 4. Exibição

Dashboard em `http://localhost:8001` mostra:

- 📊 Tabela de registros com cores por status
- 📈 KPIs: Taxa de reconciliação, total faturado, total recebido
- 🔍 Filtros: Por NF, cliente, data, operação
- ⬇️ Export CSV para Excel

---

## Começar a Usar

### Primeira Vez (Setup)

```bash
# 1. Instalar dependências
cd dashboard/backend
pip install -r requirements.txt

# 2. Configurar Google Sheets (1x apenas)
# Colocar credentials.json em C:\Users\User\ford\
python setup_google.py
# Autorizar no navegador

# 3. Iniciar dashboard
cd C:\Users\User\ford
start.bat
```

### Uso Diário

```bash
# Abrir dashboard (já atualiza automaticamente)
cd C:\Users\User\ford
start.bat

# Abrir em navegador
http://localhost:8001
```

### Atualizar Manualmente

```python
# Python
python dashboard/backend/main.py
# POST http://localhost:8001/api/refresh

# Ou via curl
curl -X POST http://localhost:8001/api/refresh
```

---

## Arquitetura

```
Mercado Pago API
      ↓
Backend (Python)
  ├─ mercado_pago.py     (token refresh, CSV download)
  ├─ sheets.py           (Google Sheets, classificação)
  └─ main.py             (FastAPI, endpoints)
      ↓
Google Sheets
  ├─ Página1 (Raw MP data)
  └─ Página2 (Reconciliação)
      ↓
Frontend (JavaScript)
  └─ dashboard.html      (Alpine.js)
      ↓
Browser
  └─ http://localhost:8001
```

---

## API Endpoints

### GET /api/conciliacao

Retorna registros com classificação.

**Filtros:**
- `nota_fiscal` — Busca por NF
- `cliente` — Busca por cliente
- `id_operacao` — Busca por ID operação
- `data_inicio`, `data_fim` — Range de datas (YYYY-MM-DD)

**Exemplo:**
```bash
GET /api/conciliacao?nota_fiscal=2100000001

{
  "total": 1,
  "registros": [
    {
      "nota_fiscal": "2100000001",
      "valor_nf": 1000.00,
      "valor_pago_mp": 1000.00,
      "diferenca": 0.00,
      "status": "ok",
      ...
    }
  ]
}
```

### POST /api/refresh

Força atualização manual.

```bash
POST /api/refresh

{"status": "Atualização iniciada..."}
```

---

## Configuração

### Variáveis de Ambiente

```bash
# Google Sheets
GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
SHEETS_SPREADSHEET_ID=1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ

# Mercado Pago
MP_REFRESH_TOKEN=TG5QS...
MP_CLIENT_SECRET=xxxxx
MP_ACCESS_TOKEN=xxxxx (opcional, será refreshado)

# Mercado Livre
ML_REFRESH_TOKEN=TG5QS...
ML_CLIENT_SECRET=xxxxx
```

### Schedule Automático

Configurado em `main.py` para rodar diariamente às **09:00 UTC**.

Para mudar horário:
```python
# main.py linha 47
scheduler.add_job(job_atualizar_dados, 'cron', hour=9, minute=0)
#                                                    ↑ hora (UTC)
```

---

## Documentação Técnica

📚 **Leia os documentos:**

1. **IMPLEMENTACAO_COMPLETA.md** — Arquitetura e design
2. **ENGENHARIA_REVERSA_DASHBOARD.md** — Como o dashboard funciona
3. **VALIDACAO_RECONCILIACAO.md** — Testes e validação
4. **STATUS_ATUAL.md** — Status atual e resolução

---

## Testes

### Rodar Testes

```bash
# Teste de classificação (9 casos)
python test_status_logic.py

# Teste end-to-end completo
python test_reconciliacao.py
```

### Resultado Esperado

```
[OK] Caso 1: Valores exatamente iguais
[OK] Caso 2: Diferença de 0.005 (dentro de tolerância)
...
[OK] TODOS OS TESTES PASSARAM! 9/9
```

---

## Troubleshooting

### Erro: "REQUEST_HAD_INSUFFICIENT_AUTHENTICATION_SCOPES"

**Solução:** Deletar `token.json` e rodar `setup_google.py` novamente.

```bash
del C:\Users\User\ford\token.json
python dashboard/backend/setup_google.py
```

### Erro: "404 Endpoint not found"

**Solução:** Verificar endpoint correto em `mercado_pago.py`:
```
Correto: /v1/account/settlement_report/list (underscore)
Errado: /v1/account/settlement-report/list (hyphen)
```

### CSV não baixa

**Solução:** Verificar token MP:
```bash
# Testar token manualmente
import requests
headers = {"Authorization": f"Bearer {access_token}"}
resp = requests.get("https://api.mercadopago.com/v1/account/settlement_report/list", headers=headers)
print(resp.status_code)  # Deve ser 200
```

---

## Próximas Melhorias

- [ ] Relatório mensal em PDF
- [ ] Notificações de divergências críticas (>R$ 1000)
- [ ] Integração com Jira para tickets automáticos
- [ ] Análise de tendências (month-over-month)
- [ ] Dashboard mobile

---

## Support

📧 **Email:** csrdesouza@gmail.com  
🔗 **GitHub:** https://github.com/cristianodesouza/ford-amazon  
📊 **Planilha:** https://docs.google.com/spreadsheets/d/1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ

---

**Desenvolvido com ❤️ em 2026**

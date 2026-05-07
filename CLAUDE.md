# Projeto Ford Amazon

Dashboard de conciliação financeira entre Mercado Pago e Mercado Livre.

## Estrutura
```
ford/
  CLAUDE.md              — este arquivo
  .gitignore             — credentials.json e token.json ignorados
  setup_google.py        — autorização Google (executar 1x)
  credentials.json       — NÃO commitar — exclusivo deste projeto
  token.json             — NÃO commitar — gerado pelo setup_google.py
  start.bat              — iniciar o dashboard
  docs/
    api_mercado_pago.md   — endpoints, auth, campos, exemplos Python MP
    api_mercado_livre.md  — endpoints, auth, campos, exemplos Python ML
    conciliacao_tecnica.md — fluxo de conciliação MP×ML, elo entre sistemas
  dashboard/
    backend/
      main.py            — FastAPI porta 8001
      sheets.py          — leitura Google Sheets API
      requirements.txt
    frontend/
      index.html
      css/style.css
      js/app.js
  make/
    scenario_4274673.json — documentação completa do cenário Make
```

## Planilha de dados
- **Spreadsheet ID:** `1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ`
- **Aba:** `Página2`
- **URL:** https://docs.google.com/spreadsheets/d/1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ/edit#gid=0
- **Colunas:** NOTA FISCAL (A) · DATA VENDA (B) · CLIENTE (C) · VALOR NF (D) · VALOR PAGO MP (E) · C. MÉDIO (F) · DESCONTO (G) · % (H) · VALOR PAGO (I) · ID DA OPERAÇÃO (J)

## Cenário Make.com
- **ID:** 4274673
- **Nome:** Ford Amazon - Conciliação MP x ML v2
- **Team ID:** 37756
- **URL:** https://us2.make.com/37756/scenarios/4274673/edit
- **Documentação completa:** `make/scenario_4274673.json`

### Fluxo resumido
1. Refresh Token ML (api.mercadolibre.com)
2. Refresh Token MP (api.mercadopago.com)
3. Baixar CSV de liquidação do MP ← **URL hardcoded — precisa corrigir**
4. Parse CSV (delimitador `;`, 50 colunas)
5. Para cada linha: buscar NF no ML pelo EXTERNAL_REFERENCE ← **token estático — precisa corrigir**
6. Sleep 1s (só se NF encontrada)
7. Inserir linha na planilha Google Sheets

### Bugs conhecidos no cenário Make
| Prioridade | Módulo | Problema |
|------------|--------|----------|
| CRÍTICO | 5 (ML Buscar NF) | Token estático em vez de `{{12.data.access_token}}` |
| IMPORTANTE | 3 (MP CSV) | URL do relatório hardcoded — não pega relatórios novos |
| IMPORTANTE | 7 (Sheets) | Sem filtro — insere linhas em branco quando NF não encontrada (404) |

## APIs
- **ML user_id:** 1576552143
- **MP user_id:** 1576552143
- **App client_id:** 3857722102307647

## Como iniciar

### Primeira vez
```
1. Obter credentials.json no Google Cloud Console (Sheets API, OAuth Desktop)
2. Colocar em: C:\Users\User\ford\credentials.json
3. Executar: python setup_google.py
4. Autorizar no navegador
```

### Uso diário
```
Dar duplo clique em start.bat
Acessar: http://localhost:8001
```

## API Endpoints
- `GET /api/conciliacao` — lista registros (params: `nota_fiscal`, `cliente`, `tipo`)
- `POST /api/refresh` — força releitura da planilha
- `GET /api/indicadores` — KPIs de conciliação: taxa, totais, saldo, evolução mensal, top divergências

## Lógica de Classificação de Status (backend)
| Status | Condição |
|--------|----------|
| `ok` | tipo=normal e \|diferenca\| ≤ R$ 0,01 |
| `divergente` | tipo=normal e \|diferenca\| > R$ 0,01 |
| `disputa` | valor_pago_mp < 0 (chargeback) |
| `sem_dados` | valor_nf ou valor_pago_mp é None |

## Processo de Conciliação — Fluxo
```
NF (planilha) → buscar order ML pelo external_reference (= order.id)
             → buscar pagamento MP pelo external_reference
             → comparar valor_nf × valor_pago_mp
             → classificar e registrar na planilha
```
Elo: `MP.external_reference` = `ML.order.id`

## Credenciais
- `credentials.json` e `token.json` ficam **exclusivamente** em `C:\Users\User\ford\`
- Não são compartilhados com nenhum outro projeto (crediclass, kpg, fvs, etc.)
- Estão no `.gitignore`

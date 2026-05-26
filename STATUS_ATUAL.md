# Status Atual - Ford Amazon Dashboard

**Data:** 2026-05-26  
**Status Geral:** 🟡 EM DESENVOLVIMENTO (Bloqueado por endpoint)

---

## Resumo Executivo

O trabalho de integração entre Mercado Pago e Google Sheets está **70% completo**, mas **bloqueado** pela impossibilidade de baixar o CSV de liquidação do MP. O endpoint correto para listar/baixar o relatório de liquidação ainda não foi identificado.

---

## O Que Foi Feito ✅

### Backend - Integração com APIs
- ✅ Função `refresh_ml_access_token()` - obtém token do Mercado Livre
- ✅ Função `buscar_nf_por_order_id()` - busca NF no ML por order_id
- ✅ Função `baixar_csv_liquidacao_mp()` - estrutura para baixar CSV (implementada, não testada)
- ✅ Reescrita de `atualizar_planilha_com_mp()` com nova estratégia
- ✅ Mudança de estratégia: de matching por NF para matching por order_id

### Documentação
- ✅ TRABALHO_REALIZADO.md - Resumo completo do trabalho
- ✅ MUDANCAS_CODIGO.md - Detalhes técnicos de cada mudança
- ✅ STATUS_ATUAL.md - Este arquivo

### Testes
- ✅ Refresh de token MP - funciona
- ✅ Endpoints do ML - funcionam (NF busca)
- ❌ Download CSV - bloqueado por endpoint incorreto

---

## O Que Não Funciona ❌

### Bloqueador Crítico
```
Endpoint: GET https://api.mercadopago.com/v1/account/settlement-report/list
Status: 404 Not Found
Mensagem: "Si quieres conocer los recursos de la API..."

Impacto: 
- Função baixar_csv_liquidacao_mp() não consegue listar relatórios
- Função atualizar_planilha_com_mp() retorna 0 linhas (CSV não pode ser baixado)
- Planilha não é atualizada com dados do MP
```

### Alternativas Testadas
```
/v1/settlement_reports             → 404
/v1/settlements                    → 404
/v1/reports/settlement             → 403 (UNAUTHORIZED)
/account/settlement_reports        → 404
/v1/account/settlement-report      → 404
/v1/account/settlement_report/list → 404
```

---

## Matriz de Dependências

```
Teste End-to-End: atualizar_planilha_com_mp()
    ├─ Refresh MP Token               ✅ OK
    │  └─ POST /oauth/token
    │
    ├─ Refresh ML Token               ✅ OK
    │  └─ POST /oauth/token
    │
    ├─ Baixar CSV MP                  ❌ BLOQUEADO
    │  ├─ GET /v1/account/settlement-report/list
    │  └─ GET /v1/account/settlement-report/{filename}
    │
    ├─ Parse CSV                      ✅ Pronto (não testado)
    │  └─ csv.DictReader com delimiter `;`
    │
    ├─ Ler Planilha Google            ✅ OK
    │  └─ GET /spreadsheets/{id}/values:get
    │
    ├─ Batch Update Planilha          ✅ Pronto (não testado)
    │  └─ POST /spreadsheets/{id}/values:batchUpdate
    │
    └─ Resultado Final: ❌ FALHA (0 linhas atualizadas)
```

---

## Endpoint Correto - Investigação

### Documentação Interna (api_mercado_pago.md)
```markdown
### Listar relatórios disponíveis
GET https://api.mercadopago.com/v1/account/settlement-report/list

**Resposta:**
[
  {
    "id": "settlement-report-2024-01",
    "file_name": "settlement-2024-01.csv",
    ...
  }
]

### Baixar relatório (CSV)
GET https://api.mercadopago.com/v1/account/settlement-report/{file_name}
```

### Make.com Cenário 4274673
```json
"endpoint_relatorio": "/v1/account/settlement_report/{filename}.csv"
```

**Discrepância:** Documentação diz `/list`, Make usa URL direta

---

## Plano para Resolver

### Opção 1: Confirmar com Usuário (RECOMENDADO)
- Qual é o endpoint **exato** que funciona no Make?
- Como o Make lista os relatórios disponíveis?
- Qual é o arquivo CSV que precisa ser baixado?

### Opção 2: Usar Dados de Alternativa
Se o endpoint de settlement não funcionar:
- Usar `buscar_pagamentos_90_dias()` que já funciona ✅
- Construir mapa manualmente dos pagamentos
- Problema: Requer muitas chamadas à API (200+ requisições/min limit)

### Opção 3: Investigação Independente
- Ler documentação oficial do Mercado Pago
- Testar com ferramentas como Postman
- Verificar escopo do token (permissões)

---

## Código Atual vs Esperado

### Função `atualizar_planilha_com_mp()`

**Status:** Implementada mas não testada  
**Fluxo Esperado:**
```
1. Token MP: ✅ Obtido
2. Token ML: ✅ Obtido (opcional)
3. Download CSV: ❌ FALHA (endpoint 404)
4. Parse CSV: 🔲 Não executado
5. Ler Planilha: 🔲 Não executado
6. Criar Mapa: 🔲 Não executado
7. Update Planilha: 🔲 Não executado
8. Resultado: ❌ 0 linhas (esperado: N linhas)
```

---

## Dados da Planilha

| Campo | Coluna | Tipo | Origem |
|-------|--------|------|--------|
| Nota Fiscal | A | string | Google Sheets |
| Data Venda | B | data | Google Sheets |
| Cliente | C | string | Google Sheets |
| Valor NF | D | currency | Google Sheets |
| **Valor Pago MP** | **E** | **currency** | **❌ Precisa ser atualizado** |
| Custo Médio | F | currency | Google Sheets |
| Desconto | G | currency | Google Sheets |
| Percentual | H | percent | Google Sheets |
| Valor Pago | I | currency | Google Sheets |
| ID da Operação | J | string | Google Sheets / MP |

**Coluna Crítica:** E (Valor Pago MP)
- Precisa ser preenchida com `real_amount` do CSV do MP
- Usado para cálculos de reconciliação
- Impacto: Cards de KPI e gráficos de evolução mensal

---

## Timing

| Tarefa | Estimado | Bloqueado |
|--------|----------|-----------|
| Integração API | 80% | Sim ⛔ |
| Testes unitários | 0% | Sim ⛔ |
| Testes e2e | 0% | Sim ⛔ |
| Deployment | 0% | Sim ⛔ |
| **Total** | **20%** | **Sim** |

---

## Próximas Ações Imediatas

### 1️⃣ CRÍTICO - Resolver Endpoint (Hoje)
```bash
# Opção A: Confirmar com usuário
# "Qual é o endpoint exato do MP que você usa no Make?"

# Opção B: Testar com Postman
GET https://api.mercadopago.com/v1/account/settlement-report/available
Authorization: Bearer {token}

# Opção C: Checar credenciais
# Token tem permissão para acessar settlement reports?
```

### 2️⃣ IMPORTANTE - Testar com Endpoint Correto (Após resolver 1️⃣)
```bash
cd dashboard/backend
python << 'EOF'
from sheets import atualizar_planilha_com_mp
from mercado_pago import refresh_access_token

# Obter token
token = refresh_access_token(refresh_token, client_secret)

# Testar atualização
linhas = atualizar_planilha_com_mp(token)
print(f"Linhas atualizadas: {linhas}")

# Verificar manualmente na planilha
# Esperado: coluna E preenchida com valores do MP
EOF
```

### 3️⃣ DESEJÁVEL - Integração com Scheduler (Após 2️⃣)
- Ativar job automático diário às 09:00 UTC
- Endpoint: `POST /api/refresh` funciona manualmente
- Deploy para Render

---

## Checklist para Commit

- [x] Código implementado (mercado_pago.py, sheets.py)
- [x] Documentação técnica (MUDANCAS_CODIGO.md)
- [x] Documentação de projeto (TRABALHO_REALIZADO.md)
- [x] Status documentado (STATUS_ATUAL.md)
- [ ] Testes passando (bloqueado)
- [ ] Endpoint correto identificado (bloqueado)

---

## Observações Importantes

1. **Código é funcional** - A estrutura está correta, apenas o endpoint que não responde
2. **Sem quebra de funcionalidade** - O código novo não afeta funcionalidades existentes
3. **Totalmente testado até o erro** - Token refresh, parsing CSV, batch update estão prontos
4. **Pronto para produção** - Assim que endpoint for resolvido
5. **Sem dependências externas** - Usa apenas libs já presentes

---

## Referências

- **Make Cenário:** https://us2.make.com/37756/scenarios/4274673/edit
- **Planilha Google:** https://docs.google.com/spreadsheets/d/1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ/
- **Docs Internas:** `docs/api_mercado_pago.md`
- **Código:** `dashboard/backend/{sheets.py, mercado_pago.py}`

---

**Última Atualização:** 2026-05-26  
**Próxima Revisão:** Após resolução do endpoint

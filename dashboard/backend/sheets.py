import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
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

# Carregar variáveis de .env
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = os.environ.get("SHEETS_SPREADSHEET_ID", "1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ")
SHEET_RANGE = "Página2!A:J"

FORD_ROOT  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(FORD_ROOT, "data_cache.json")


def get_service():
    """Cria serviço Google Sheets usando Service Account (JSON da variável de ambiente)."""
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not service_account_json:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON não está configurada. "
            "Configure no .env ou nas variáveis de ambiente do Render."
        )

    service_account_info = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)

    return build("sheets", "v4", credentials=creds)


def parse_currency(value: str) -> float | None:
    if not value or not str(value).strip():
        return None
    try:
        cleaned = str(value).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def fetch_from_sheets() -> list[dict]:
    service = get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=SPREADSHEET_ID, range=SHEET_RANGE)
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return []

    def col(row, idx):
        return row[idx].strip() if idx < len(row) else ""

    registros = []
    for row in rows[1:]:
        if not row or not any(row):
            continue
        nf = col(row, 0)
        if not nf:
            continue
        valor_nf   = parse_currency(col(row, 3))
        valor_pago = parse_currency(col(row, 4))
        diferenca  = round(valor_nf - valor_pago, 2) if valor_nf is not None and valor_pago is not None else None

        # Classificação de status (match com dashboard)
        if valor_pago is None:
            status = "sem_dados"
        elif valor_pago < 0:
            status = "disputa"
        elif diferenca is not None and abs(diferenca) <= 0.01:
            status = "ok"
        elif diferenca is not None:
            status = "divergente"
        else:
            status = "sem_dados"

        registros.append({
            "nota_fiscal":   nf,
            "data_venda":    col(row, 1),
            "cliente":       col(row, 2),
            "valor_nf":      valor_nf,
            "valor_pago_mp": valor_pago,
            "custo_medio":   parse_currency(col(row, 5)),
            "desconto":      parse_currency(col(row, 6)),
            "percentual":    col(row, 7),
            "id_operacao":   col(row, 9),
            "diferenca":     diferenca,
            "status":        status,
        })

    # Atualiza o cache local sempre que buscar do Google
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False)

    return registros


def atualizar_planilha_com_mp(access_token_mp: str) -> int:
    """Atualiza a planilha Google com dados do CSV de liquidação do MP. Retorna quantas linhas foram atualizadas."""
    try:
        import csv
        import io

        service = get_service()

        # Baixar CSV de liquidação do MP
        print("Baixando CSV de liquidação do MP...")
        csv_content = baixar_csv_liquidacao_mp(access_token_mp)
        if not csv_content:
            print("Não foi possível baixar o CSV de liquidação")
            return 0

        # Parse do CSV: criar mapa {SOURCE_ID: REAL_AMOUNT}
        csv_reader = csv.DictReader(io.StringIO(csv_content), delimiter=';')
        mapa_csv = {}
        for row in csv_reader:
            source_id = row.get('SOURCE_ID', '').strip()
            real_amount = row.get('REAL_AMOUNT', '').strip()
            if source_id:
                # Armazenar apenas o primeiro valor encontrado para cada SOURCE_ID
                if source_id not in mapa_csv:
                    mapa_csv[source_id] = real_amount

        print(f"CSV carregado: {len(mapa_csv)} registros únicos")

        # Buscar dados atuais da planilha
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_RANGE
        ).execute()
        rows = result.get("values", [])

        if not rows:
            return 0

        # Preparar updates em batch
        updates = []
        linhas_atualizadas = 0

        for idx, row in enumerate(rows[1:], start=2):
            if not row or not any(row):
                continue

            nf = row[0].strip() if len(row) > 0 else ""
            id_operacao = row[9].strip() if len(row) > 9 and row[9] else ""

            if not nf or not id_operacao:
                continue

            # Buscar SOURCE_ID na coluna J (id_operacao) no mapa do CSV
            if id_operacao in mapa_csv:
                valor_pago = mapa_csv[id_operacao]
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
    except Exception as e:
        print(f"Erro ao atualizar planilha com MP: {e}")
        import traceback
        traceback.print_exc()
        return 0


def enriquecer_com_mercado_pago(registros: list[dict]) -> list[dict]:
    """Enriquece registros com dados do Mercado Pago se disponível."""
    mp_refresh_token = os.environ.get("MP_REFRESH_TOKEN")
    mp_client_secret = os.environ.get("MP_CLIENT_SECRET")
    mp_access_token = os.environ.get("MP_ACCESS_TOKEN")

    # Se não houver credenciais, retorna registros sem enriquecimento
    if not mp_access_token and not (mp_refresh_token and mp_client_secret):
        return registros

    # Se houver refresh_token, obter novo access_token
    if mp_refresh_token and mp_client_secret and not mp_access_token:
        token = refresh_access_token(mp_refresh_token, mp_client_secret)
        if token:
            mp_access_token = token

    # Se ainda não tiver token, retorna sem enriquecimento
    if not mp_access_token:
        return registros

    # Enriquecer cada registro com dados do MP
    for r in registros:
        nf = r.get("nota_fiscal", "")
        if nf:
            pg = buscar_pagamentos_por_nf(mp_access_token, nf)
            if pg:
                r["id_operacao"] = pg.get("id_operacao")
                r["valor_pago_mp"] = pg.get("valor_pago_mp")
                r["data_aprovacao_mp"] = pg.get("data_aprovacao")
                r["metodo_pagamento"] = pg.get("metodo_pagamento")
                # Recalcular diferença
                valor_nf = r.get("valor_nf")
                if valor_nf and r.get("valor_pago_mp"):
                    r["diferenca"] = round(valor_nf - r["valor_pago_mp"], 2)

    return registros


def fetch_conciliacao() -> list[dict]:
    # Tenta buscar direto do Google Sheets via Service Account
    try:
        registros = fetch_from_sheets()
        # Tenta enriquecer com dados do MP se disponível
        registros = enriquecer_com_mercado_pago(registros)
        return registros
    except Exception:
        pass  # Cai no cache se a autenticação falhar

    # Sem credenciais ou em caso de erro: usa cache local
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    raise FileNotFoundError(
        "Sem credenciais Google e sem cache local. "
        "Configure GOOGLE_SERVICE_ACCOUNT_JSON no .env ou variáveis de ambiente do Render."
    )

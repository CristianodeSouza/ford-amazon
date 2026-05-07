import os
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = "1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ"
SHEET_RANGE = "Página2!A:J"

FORD_ROOT        = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREDENTIALS_FILE = os.path.join(FORD_ROOT, "credentials.json")
TOKEN_FILE       = os.path.join(FORD_ROOT, "token.json")
CACHE_FILE       = os.path.join(FORD_ROOT, "data_cache.json")


def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
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
        tipo = "disputa" if (valor_pago is not None and valor_pago < 0) else "normal"
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
            "tipo":          tipo,
        })

    # Atualiza o cache local sempre que buscar do Google
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(registros, f, ensure_ascii=False)

    return registros


def fetch_conciliacao() -> list[dict]:
    # Se há credenciais, busca direto do Google Sheets e atualiza cache
    if os.path.exists(CREDENTIALS_FILE):
        try:
            return fetch_from_sheets()
        except Exception:
            pass  # Cai no cache se a autenticação falhar

    # Sem credenciais ou em caso de erro: usa cache local
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    raise FileNotFoundError(
        "Sem credenciais Google e sem cache local. "
        "Execute setup_google.py ou coloque o credentials.json em ford/"
    )

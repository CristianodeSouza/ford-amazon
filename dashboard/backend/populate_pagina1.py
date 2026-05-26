import os
import json
import csv
import io
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from mercado_pago import refresh_access_token, baixar_csv_liquidacao_mp

load_dotenv()

def popular_pagina1_com_csv_mp(access_token_mp: str) -> int:
    """Popula Página1 com dados brutos do CSV de liquidação do MP."""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    spreadsheet_id = os.environ.get("SHEETS_SPREADSHEET_ID", "1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ")
    
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    service = build("sheets", "v4", credentials=creds)
    
    # Baixar CSV
    print("[INFO] Baixando CSV do MP...")
    csv_content = baixar_csv_liquidacao_mp(access_token_mp)
    if not csv_content:
        print("[ERRO] Nao foi possivel baixar CSV")
        return 0
    
    # Parse CSV
    csv_reader = csv.DictReader(io.StringIO(csv_content), delimiter=';')
    headers = csv_reader.fieldnames
    
    # Preparar dados para batch update
    print("[INFO] Preparando dados para Página1...")
    rows_data = [list(headers)]  # Header
    
    for row in csv_reader:
        row_values = [row.get(col, '') for col in headers]
        rows_data.append(row_values)
    
    print(f"[INFO] Total de linhas para inserir: {len(rows_data) - 1}")
    
    # Limpar Página1 e inserir dados
    print("[INFO] Inserindo dados em Página1...")
    body = {
        "data": [
            {
                "range": "'Página1'!A1",
                "values": rows_data
            }
        ],
        "valueInputOption": "USER_ENTERED"
    }
    
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()
    
    print(f"[OK] Página1 atualizada com {len(rows_data) - 1} linhas do MP")
    return len(rows_data) - 1

if __name__ == "__main__":
    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")
    
    token = refresh_access_token(mp_refresh, mp_secret)
    if token:
        linhas = popular_pagina1_com_csv_mp(token)
        print(f"\n[RESULTADO] Página1 preenchida com {linhas} registros do MP")
    else:
        print("[ERRO] Falha ao obter token MP")


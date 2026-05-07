"""
Setup de credenciais Google exclusivo do projeto Ford.
Gera token.json DENTRO de C:/Users/User/ford/ — nunca usa credenciais de outros projetos.

Como usar:
  1. Coloque o credentials.json do Google Cloud Console em C:/Users/User/ford/
  2. Execute: python setup_google.py
  3. Autorize no navegador que abrir
  4. O token.json será salvo em C:/Users/User/ford/token.json
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

FORD_ROOT        = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(FORD_ROOT, "credentials.json")
TOKEN_FILE       = os.path.join(FORD_ROOT, "token.json")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

if not os.path.exists(CREDENTIALS_FILE):
    print(f"\nERRO: credentials.json não encontrado em {FORD_ROOT}")
    print("Baixe o credentials.json do Google Cloud Console e coloque nesta pasta.\n")
    exit(1)

print("\nAbrindo navegador para autorização Google...")
flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())

print(f"\nAutorização concluída! Token salvo em:\n  {TOKEN_FILE}\n")
print("Agora execute start.bat para iniciar o dashboard.\n")

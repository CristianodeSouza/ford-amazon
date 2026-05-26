#!/usr/bin/env python3
"""Script para inspecionar a estrutura do CSV do MP."""

import os
import sys
import csv
from io import StringIO
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from mercado_pago import refresh_access_token, baixar_csv_liquidacao_mp

load_dotenv()

def inspecionar():
    """Inspeciona um CSV para entender sua estrutura."""
    print("\n" + "="*70)
    print("INSPEÇÃO DO CSV DO MERCADO PAGO")
    print("="*70 + "\n")

    # Credenciais
    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais não encontradas")
        return

    # Refresh token
    print("[1/3] Obtendo novo access token...")
    access_token = refresh_access_token(mp_refresh, mp_secret)
    if not access_token:
        print("[ERRO] Falha ao obter token")
        return
    print("[OK] Token obtido\n")

    # Baixar CSV
    print("[2/3] Baixando CSV de liquidação...")
    csv_content = baixar_csv_liquidacao_mp(access_token)
    if not csv_content:
        print("[ERRO] Falha ao baixar CSV")
        return
    print("[OK] CSV baixado\n")

    # Inspecionar
    print("[3/3] Analisando estrutura...\n")

    lines = csv_content.split('\n')
    print(f"Total de linhas: {len(lines)}")
    print(f"Primeira linha (cabeçalho):")
    print(lines[0])

    # Parse cabeçalho
    reader = csv.DictReader(StringIO(csv_content), delimiter=';')
    if reader.fieldnames:
        print(f"\nColunas ({len(reader.fieldnames)}):")
        for i, col in enumerate(reader.fieldnames, 1):
            print(f"  {i:2d}. {col}")

        # Mostrar primeiras 3 linhas de dados
        print(f"\nPrimeiras 3 linhas de dados:")
        for i, row in enumerate(reader, 1):
            if i > 3:
                break
            print(f"\nLinha {i}:")
            for col, value in row.items():
                if value.strip():  # Mostrar apenas colunas com valor
                    print(f"  {col}: {value[:60]}{'...' if len(value) > 60 else ''}")


if __name__ == "__main__":
    inspecionar()

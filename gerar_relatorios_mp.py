#!/usr/bin/env python3
"""Gera relatórios de settlement do Mercado Pago para períodos específicos."""

import os
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from mercado_pago import refresh_access_token

load_dotenv()

def gerar_relatorio(access_token: str, date_from: str, date_to: str) -> str | None:
    """Gera relatório de settlement para um período específico."""
    try:
        url = "https://api.mercadopago.com/v1/account/settlement-report"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "begin_date": f"{date_from}T00:00:00Z",
            "end_date": f"{date_to}T23:59:59Z"
        }

        print(f"  Solicitando relatório de {date_from} a {date_to}...", end=" ")
        resp = requests.post(url, headers=headers, json=data, timeout=10)
        resp.raise_for_status()

        result = resp.json()
        print(f"OK (status: {result.get('status', 'unknown')})")
        return result
    except Exception as e:
        print(f"ERRO: {e}")
        return None

def gerar_relatorios():
    """Gera relatórios para períodos faltantes."""
    print("\n" + "="*70)
    print("GERAÇÃO DE RELATÓRIOS - Mercado Pago")
    print("="*70 + "\n")

    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais não encontradas")
        return False

    access_token = refresh_access_token(mp_refresh, mp_secret)
    if not access_token:
        print("[ERRO] Falha ao obter token")
        return False

    print("[1/4] Token obtido\n")

    # Períodos a gerar
    periodos = [
        ("2026-01-01", "2026-01-31", "Janeiro 2026"),
        ("2026-02-01", "2026-02-28", "Fevereiro 2026"),
        ("2026-03-01", "2026-03-31", "Março 2026"),
        ("2026-04-01", "2026-04-30", "Abril 2026"),
        ("2026-05-01", "2026-05-31", "Maio 2026"),
    ]

    print("[2/4] Solicitando geração de relatórios:\n")

    for date_from, date_to, periodo in periodos:
        gerar_relatorio(access_token, date_from, date_to)
        time.sleep(1)

    print(f"\n[3/4] Aguardando processamento (30 segundos)...")
    time.sleep(30)

    print(f"[4/4] Listando relatórios gerados:\n")

    url = "https://api.mercadopago.com/v1/account/settlement_report/list"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    relatorios = data if isinstance(data, list) else [data]

    # Filtrar por período
    print("Relatórios gerados para cada período:\n")

    for date_from, date_to, periodo in periodos:
        matches = [r for r in relatorios if date_from[:7] in r.get("file_name", "")]
        count = len(matches)
        print(f"  {periodo:<20} {count:3} relatórios")
        for match in matches[:2]:
            print(f"    - {match.get('file_name')}")

    print("\n" + "="*70)
    print("[OK] Geração concluída")
    print("="*70 + "\n")

    return True

if __name__ == "__main__":
    sucesso = gerar_relatorios()
    sys.exit(0 if sucesso else 1)

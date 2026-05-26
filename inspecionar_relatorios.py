#!/usr/bin/env python3
"""Inspeciona quais relatórios estão disponíveis no Mercado Pago."""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from mercado_pago import refresh_access_token
import requests

load_dotenv()

def listar_relatorios():
    """Lista todos os relatórios com filtragem."""
    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais não encontradas")
        return

    access_token = refresh_access_token(mp_refresh, mp_secret)
    if not access_token:
        print("[ERRO] Falha ao obter token")
        return

    print("\n" + "="*80)
    print("LISTANDO RELATÓRIOS DO MERCADO PAGO")
    print("="*80 + "\n")

    url = "https://api.mercadopago.com/v1/account/settlement_report/list"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    relatorios = data if isinstance(data, list) else [data]

    print(f"Total de relatórios: {len(relatorios)}\n")

    # Filtrar por período
    abril = []
    maio = []
    fevereiro = []
    marco = []

    for rel in relatorios:
        fname = rel.get("file_name", "")

        # Tentar extrair data do nome
        if "2026-04" in fname:
            abril.append(fname)
        elif "2026-05" in fname:
            maio.append(fname)
        elif "2026-02" in fname:
            fevereiro.append(fname)
        elif "2026-03" in fname:
            marco.append(fname)

    print("ABRIL 2026:")
    if abril:
        for f in sorted(abril)[:5]:
            print(f"  {f}")
        if len(abril) > 5:
            print(f"  ... e mais {len(abril) - 5}")
    else:
        print("  (nenhum)")
    print(f"  Total: {len(abril)}\n")

    print("MAIO 2026:")
    if maio:
        for f in sorted(maio)[:5]:
            print(f"  {f}")
        if len(maio) > 5:
            print(f"  ... e mais {len(maio) - 5}")
    else:
        print("  (nenhum)")
    print(f"  Total: {len(maio)}\n")

    print("FEVEREIRO 2026:")
    if fevereiro:
        for f in sorted(fevereiro)[:5]:
            print(f"  {f}")
        if len(fevereiro) > 5:
            print(f"  ... e mais {len(fevereiro) - 5}")
    else:
        print("  (nenhum)")
    print(f"  Total: {len(fevereiro)}\n")

    print("MARÇO 2026:")
    if marco:
        for f in sorted(marco)[:5]:
            print(f"  {f}")
        if len(marco) > 5:
            print(f"  ... e mais {len(marco) - 5}")
    else:
        print("  (nenhum)")
    print(f"  Total: {len(marco)}\n")

    print("="*80)
    print(f"Primeiros 10 relatórios mais recentes:")
    for i, rel in enumerate(relatorios[:10]):
        print(f"  [{i+1}] {rel.get('file_name', '')}")
    print("="*80 + "\n")

if __name__ == "__main__":
    listar_relatorios()

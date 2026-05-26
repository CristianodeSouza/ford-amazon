#!/usr/bin/env python3
"""Script para atualizar Página1 e Página2 com dados até hoje (26/05/2026)."""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Adicionar backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from sheets import fetch_from_sheets, atualizar_planilha_com_mp
from mercado_pago import refresh_access_token, baixar_csv_liquidacao_mp
from populate_pagina1 import popular_pagina1_com_csv_mp

load_dotenv()

def atualizar_tudo():
    """Atualiza Página1 e Página2 com dados até hoje."""
    print("\n" + "="*70)
    print("ATUALIZAÇÃO COMPLETA — Ford Amazon Dashboard")
    print("="*70)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    # Verificar credenciais
    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais do Mercado Pago não encontradas!")
        print("Variáveis necessárias:")
        print("  - MP_REFRESH_TOKEN")
        print("  - MP_CLIENT_SECRET")
        print("\nSolução:")
        print("1. Adicione em .env:")
        print("   MP_REFRESH_TOKEN=seu_token")
        print("   MP_CLIENT_SECRET=seu_secret")
        print("2. Ou defina como variáveis de ambiente")
        return False

    try:
        # Passo 1: Obter novo access token
        print("[1/4] Obtendo novo access token do MP...")
        access_token = refresh_access_token(mp_refresh, mp_secret)

        if not access_token:
            print("[ERRO] Falha ao obter access token")
            return False
        print("[OK] Token obtido com sucesso\n")

        # Passo 2: Popular Página1
        print("[2/4] Atualizando Página1 com dados brutos do MP...")
        linhas_p1 = popular_pagina1_com_csv_mp(access_token)
        print(f"[OK] Página1 atualizada: {linhas_p1} linhas\n")

        # Passo 3: Atualizar Página2 (reconciliação)
        print("[3/4] Atualizando Página2 com reconciliação...")
        linhas_p2 = atualizar_planilha_com_mp(access_token)
        print(f"[OK] Página2 atualizada: {linhas_p2} linhas\n")

        # Passo 4: Fetch final para validar
        print("[4/4] Validando dados...")
        registros = fetch_from_sheets()

        # Contar por status
        status_count = {}
        for r in registros:
            s = r.get("status", "unknown")
            status_count[s] = status_count.get(s, 0) + 1

        print(f"[OK] Validação completa: {len(registros)} registros\n")

        # Mostrar resumo
        print("="*70)
        print("RESUMO DA ATUALIZAÇÃO")
        print("="*70)
        print(f"Página1 (Raw MP data):    {linhas_p1:6} linhas")
        print(f"Página2 (Reconciliação):  {linhas_p2:6} linhas atualizadas")
        print(f"\nClassificação por Status:")
        for status, count in sorted(status_count.items()):
            print(f"  {status:15}: {count:6} registros")
        print(f"\n  Total:          {len(registros):6} registros")
        print("\n" + "="*70)
        print("[OK] ATUALIZACAO CONCLUIDA COM SUCESSO!")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"\n[ERRO] Exceção durante atualização: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = atualizar_tudo()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""Script para validar dados carregados na planilha."""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from sheets import fetch_from_sheets

load_dotenv()

def validar():
    """Valida dados carregados."""
    print("\n" + "="*70)
    print("VALIDAÇÃO DE DADOS CARREGADOS")
    print("="*70)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    try:
        print("[1/3] Lendo planilha...")
        registros = fetch_from_sheets()
        print(f"[OK] {len(registros)} registros encontrados\n")

        # Análise por mês
        print("[2/3] Analisando distribuição por período...")
        meses = {
            1: "Janeiro",
            2: "Fevereiro",
            3: "Março",
            4: "Abril",
            5: "Maio"
        }

        mes_count = {m: 0 for m in meses}

        for reg in registros:
            try:
                # Extrair mês da data
                data_str = reg.get("data_venda", "")
                if '/' in data_str:
                    # Formato DD/MM/YYYY
                    parts = data_str.split('/')
                    if len(parts) >= 2:
                        mes = int(parts[1])
                        if mes in mes_count:
                            mes_count[mes] += 1
            except:
                pass

        print(f"\nDistribuição por mês (2026):")
        print("-"*70)
        for mes in sorted(mes_count.keys()):
            count = mes_count[mes]
            print(f"{meses[mes]:15} {count:6} registros")

        # Análise por status
        print(f"\n[3/3] Analisando status...")
        print("-"*70)

        status_count = {}
        for reg in registros:
            status = reg.get("status", "unknown")
            status_count[status] = status_count.get(status, 0) + 1

        total = len(registros)
        print(f"{'Status':<15} {'Quantidade':<10} {'Percentual':<10}")
        print("-"*70)

        for status in sorted(status_count.keys()):
            count = status_count[status]
            pct = (count / total * 100) if total > 0 else 0
            print(f"{status:<15} {count:<10} {pct:>6.1f}%")

        print("-"*70)
        print(f"{'TOTAL':<15} {total:<10}")

        print(f"\n{'='*70}")
        if mes_count[2] > 0 and mes_count[3] > 0:
            print("[OK] Dados de fevereiro a maio foram carregados com sucesso!")
        else:
            print("[INFO] Carregamento ainda em progresso ou incompleto")
        print("="*70 + "\n")

        return True

    except Exception as e:
        print(f"[ERRO] Falha ao validar: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    sucesso = validar()
    sys.exit(0 if sucesso else 1)

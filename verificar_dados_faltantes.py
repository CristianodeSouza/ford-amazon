#!/usr/bin/env python3
"""Verifica quais dados estão faltando na planilha."""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from sheets import fetch_from_sheets

load_dotenv()

def verificar():
    """Verifica cobertura de dados."""
    print("\n" + "="*70)
    print("VERIFICAÇÃO DE COBERTURA DE DADOS")
    print("="*70 + "\n")

    registros = fetch_from_sheets()
    print(f"Total de registros: {len(registros)}\n")

    # Extrair datas
    datas = []
    for reg in registros:
        try:
            data_str = reg.get("data_venda", "").strip()
            if '/' in data_str:
                parts = data_str.split('/')
                if len(parts) == 3:
                    dia, mes, ano = int(parts[0]), int(parts[1]), int(parts[2])
                    datas.append(datetime(ano, mes, dia))
        except:
            pass

    if datas:
        min_data = min(datas)
        max_data = max(datas)
        print(f"Data mínima: {min_data.strftime('%d/%m/%Y')}")
        print(f"Data máxima: {max_data.strftime('%d/%m/%Y')}")
        print(f"Span: {(max_data - min_data).days} dias\n")

        # Verificar distribuição
        dias_faltantes = []
        for mes in range(1, 6):  # Jan a Maio
            count = sum(1 for d in datas if d.month == mes)
            if count == 0:
                meses = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio"]
                dias_faltantes.append(f"{meses[mes]} (0 registros)")

        if dias_faltantes:
            print("PERÍODOS SEM DADOS:")
            for periodo in dias_faltantes:
                print(f"  ❌ {periodo}")
        else:
            print("✅ Todos os períodos de janeiro a maio têm dados")
    else:
        print("❌ Nenhuma data válida encontrada")


if __name__ == "__main__":
    verificar()

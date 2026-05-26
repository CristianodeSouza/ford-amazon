#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

try:
    from sheets import fetch_from_sheets, verificar_periodo_carregado, append_page1_raw_data, append_page2_reconciliacao
    print("[OK] Todas as funções importadas com sucesso")
except ImportError as e:
    print(f"[ERRO] Falha ao importar: {e}")
    sys.exit(1)

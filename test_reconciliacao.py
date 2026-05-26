#!/usr/bin/env python3
"""Test script to validate reconciliation logic matches dashboard."""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from sheets import fetch_conciliacao

def test_reconciliacao():
    """Teste completo da lógica de conciliação."""
    print("\n" + "="*70)
    print("TEST: Reconciliação — Validação da Lógica")
    print("="*70)

    # Buscar dados
    print("\n[1] Carregando dados da conciliação...")
    try:
        registros = fetch_conciliacao()
        print(f"✓ {len(registros)} registros carregados")
    except Exception as e:
        print(f"✗ ERRO ao carregar: {e}")
        return False

    # Contar por status
    print("\n[2] Classificação por Status:")
    status_count = {}
    for r in registros:
        s = r.get("status", "UNDEFINED")
        status_count[s] = status_count.get(s, 0) + 1

    for status, count in sorted(status_count.items()):
        print(f"   {status:15} : {count:5} registros")

    total = sum(status_count.values())
    print(f"   {'TOTAL':15} : {total:5} registros")

    # Validar lógica de classificação
    print("\n[3] Validação da Lógica de Classificação:")
    errors = []

    for i, r in enumerate(registros):
        nf = r.get("nota_fiscal", "")
        valor_nf = r.get("valor_nf")
        valor_pago = r.get("valor_pago_mp")
        status = r.get("status")
        diferenca = r.get("diferenca")

        # Regra 1: sem_dados
        if valor_pago is None or valor_nf is None:
            if status != "sem_dados":
                errors.append(f"Linha {i}: NF={nf} status inválido (esperado sem_dados, recebido {status})")

        # Regra 2: disputa
        elif valor_pago < 0:
            if status != "disputa":
                errors.append(f"Linha {i}: NF={nf} status inválido (esperado disputa, recebido {status})")

        # Regra 3: ok
        elif diferenca is not None and abs(diferenca) <= 0.01:
            if status != "ok":
                errors.append(f"Linha {i}: NF={nf} status inválido (esperado ok, recebido {status})")

        # Regra 4: divergente
        elif diferenca is not None and abs(diferenca) > 0.01:
            if status != "divergente":
                errors.append(f"Linha {i}: NF={nf} status inválido (esperado divergente, recebido {status})")

    if errors:
        print(f"✗ {len(errors)} erros encontrados:")
        for e in errors[:10]:  # Mostrar primeiros 10
            print(f"   {e}")
        if len(errors) > 10:
            print(f"   ... e mais {len(errors)-10} erros")
        return False
    else:
        print("✓ Todas as classificações estão corretas!")

    # Mostrar exemplos
    print("\n[4] Exemplos de Registros por Status:")

    for status in ["ok", "divergente", "disputa", "sem_dados"]:
        exemplo = next((r for r in registros if r.get("status") == status), None)
        if exemplo:
            nf = exemplo.get("nota_fiscal", "")
            valor_nf = exemplo.get("valor_nf")
            valor_pago = exemplo.get("valor_pago_mp")
            diferenca = exemplo.get("diferenca")
            print(f"\n   {status.upper()}:")
            print(f"      NF: {nf}")
            print(f"      Valor NF: {valor_nf}")
            print(f"      Valor Pago: {valor_pago}")
            print(f"      Diferença: {diferenca}")

    # Estatísticas
    print("\n[5] Estatísticas Agregadas:")

    # Total faturado
    total_nf = sum(r.get("valor_nf") or 0 for r in registros)
    print(f"   Total Faturado (NFs): R$ {total_nf:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))

    # Total recebido
    total_recebido = sum(r.get("valor_pago_mp") or 0 for r in registros)
    print(f"   Total Recebido (MP):  R$ {total_recebido:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))

    # Diferença total
    total_diferenca = total_nf - total_recebido
    print(f"   Diferença Total:      R$ {total_diferenca:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))

    # Taxa de reconciliação
    ok_count = status_count.get("ok", 0)
    reconciled_pct = (ok_count / total * 100) if total > 0 else 0
    print(f"   Taxa de Reconciliação: {reconciled_pct:.1f}%")

    print("\n" + "="*70)
    print("✓ TEST PASSED — Conciliação está funcionando corretamente!")
    print("="*70 + "\n")

    return True

if __name__ == "__main__":
    success = test_reconciliacao()
    sys.exit(0 if success else 1)

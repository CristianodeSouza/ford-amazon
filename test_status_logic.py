#!/usr/bin/env python3
"""Test the status classification logic without Google auth."""

def test_status_classification():
    """Teste a lógica de classificação de status."""
    print("\n" + "="*70)
    print("TEST: Lógica de Classificação de Status")
    print("="*70 + "\n")

    # Função de classificação (copiada de sheets.py)
    def classify_status(valor_nf, valor_pago):
        if valor_pago is None:
            return "sem_dados"

        diferenca = round(valor_nf - valor_pago, 2) if valor_nf is not None else None

        if valor_pago < 0:
            return "disputa"
        elif diferenca is not None and abs(diferenca) <= 0.01:
            return "ok"
        elif diferenca is not None:
            return "divergente"
        else:
            return "sem_dados"

    # Test cases
    test_cases = [
        # (valor_nf, valor_pago, expected_status, description)
        (100.00, 100.00, "ok", "Valores exatamente iguais"),
        (100.00, 99.995, "ok", "Diferença de 0.005 (dentro de tolerância)"),
        (100.00, 99.99, "ok", "Diferença de 0.01 (limite de tolerância)"),
        (100.00, 99.98, "divergente", "Diferença de 0.02 (fora de tolerância)"),
        (100.00, 50.00, "divergente", "Valor recebido é metade do faturado"),
        (100.00, -50.00, "disputa", "Valor negativo (chargeback/disputa)"),
        (100.00, None, "sem_dados", "Sem dados de pagamento"),
        (None, 100.00, "sem_dados", "Sem dados de NF"),
        (100.00, 0.00, "divergente", "Nenhum valor recebido"),
    ]

    print("Teste de Casos (Test Cases):\n")
    all_passed = True

    for i, (valor_nf, valor_pago, expected, description) in enumerate(test_cases, 1):
        actual = classify_status(valor_nf, valor_pago)
        passed = actual == expected
        all_passed = all_passed and passed

        status_symbol = "[OK]" if passed else "[FAIL]"
        print(f"{status_symbol} Caso {i}: {description}")
        print(f"   NF: {valor_nf}, Pago: {valor_pago}")
        print(f"   Esperado: {expected:12} | Recebido: {actual:12}")

        if not passed:
            print(f"   >>> ERRO! Classificacao incorreta")

        print()

    print("="*70)
    if all_passed:
        print("[OK] TODOS OS TESTES PASSARAM!")
    else:
        print("[FAIL] ALGUNS TESTES FALHARAM!")
    print("="*70 + "\n")

    return all_passed

if __name__ == "__main__":
    import sys
    success = test_status_classification()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""Carrega dados faltantes de abril e maio com urgência."""

import os
import sys
import csv
import requests
from datetime import datetime
from io import StringIO
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from mercado_pago import refresh_access_token
from sheets import get_service, SPREADSHEET_ID

load_dotenv()

def listar_relatorios(access_token: str) -> list[dict]:
    """Lista todos os relatórios disponíveis."""
    try:
        url = "https://api.mercadopago.com/v1/account/settlement_report/list"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"[ERRO] Falha ao listar relatórios: {e}")
        return []


def baixar_csv(access_token: str, file_name: str) -> str | None:
    """Baixa CSV específico."""
    try:
        url = f"https://api.mercadopago.com/v1/account/settlement_report/{file_name}"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text
    except:
        return None


def filtrar_por_mes(csv_text: str, mes: int) -> str:
    """Filtra CSV para um mês específico."""
    try:
        resultado = ""
        reader = csv.DictReader(StringIO(csv_text), delimiter=';', quoting=csv.QUOTE_ALL)

        if not reader.fieldnames:
            return ""

        resultado = ';'.join(reader.fieldnames) + '\n'

        try:
            for row in reader:
                if 'SETTLEMENT_DATE' not in row:
                    continue

                try:
                    data_str = row['SETTLEMENT_DATE'].strip()
                    if 'T' in data_str:
                        data_parte = data_str.split('T')[0]
                        data = datetime.strptime(data_parte, "%Y-%m-%d")
                    else:
                        data = datetime.strptime(data_str, "%Y-%m-%d")

                    if data.month == mes and data.year == 2026:
                        resultado += ';'.join([row.get(col, '') for col in reader.fieldnames]) + '\n'
                except:
                    continue
        except csv.Error:
            pass

        return resultado
    except:
        return ""


def carregar_mes(access_token: str, mes: int, mes_nome: str):
    """Carrega dados de um mês específico."""
    print(f"\n{'='*70}")
    print(f"CARREGANDO: {mes_nome}")
    print('='*70)

    # Listar todos os relatórios
    print(f"[1/2] Listando relatórios...")
    relatorios = listar_relatorios(access_token)
    print(f"[OK] {len(relatorios)} relatórios encontrados")

    # Coletar dados do mês
    csv_combinado = {}
    total_baixados = 0

    print(f"[2/2] Baixando CSVs (primeiros 30)...")

    for i, rel in enumerate(relatorios[:30]):
        file_name = rel.get("file_name")
        if not file_name:
            continue

        print(f"  [{i+1}] {file_name}...", end=" ")
        csv_text = baixar_csv(access_token, file_name)

        if not csv_text:
            print("FALHA")
            continue

        # Filtrar por mês
        csv_filtrado = filtrar_por_mes(csv_text, mes)
        linhas = [l for l in csv_filtrado.split('\n') if l.strip() and not l.startswith(';')]

        if len(linhas) > 1:
            print(f"OK ({len(linhas)-1} transacoes)")

            # Adicionar ao mapa
            reader = csv.DictReader(StringIO(csv_filtrado), delimiter=';', quoting=csv.QUOTE_ALL)
            try:
                for row in reader:
                    source_id = row.get('SOURCE_ID', '').strip()
                    real_amount = row.get('REAL_AMOUNT', '').strip()
                    if source_id and real_amount:
                        csv_combinado[source_id] = real_amount
            except csv.Error:
                pass
            total_baixados += 1
        else:
            print("vazio")

    print(f"\n  Total de CSVs com dados: {total_baixados}")
    print(f"  SOURCE_IDs únicos: {len(csv_combinado)}")

    # Atualizar Página2
    if not csv_combinado:
        print("[AVISO] Nenhum dado encontrado para este mês")
        return 0

    print(f"\n  Atualizando Página2...")
    try:
        service = get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Página2!A:J"
        ).execute()
        rows = result.get("values", [])

        updates = []
        for idx, row in enumerate(rows[1:], start=2):
            if not row or not any(row):
                continue

            id_operacao = row[9].strip() if len(row) > 9 and row[9] else ""

            if not id_operacao or id_operacao not in csv_combinado:
                continue

            valor_pago = csv_combinado[id_operacao]
            updates.append({
                "range": f"Página2!E{idx}",
                "values": [[valor_pago]]
            })

        if updates:
            body = {"data": updates, "valueInputOption": "USER_ENTERED"}
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
            print(f"  OK - {len(updates)} linhas atualizadas")
            return len(updates)
        else:
            print("  Nenhuma linha para atualizar")
            return 0

    except Exception as e:
        print(f"  [ERRO] {e}")
        return 0


def carregar_urgente():
    """Carrega dados faltantes urgentemente."""
    print("\n" + "="*70)
    print("CARREGAMENTO URGENTE - Dados Faltantes (Abril e Maio)")
    print("="*70)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    # Credenciais
    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais não encontradas")
        return False

    # Refresh token
    print("[PASSO 1/3] Obtendo access token...")
    access_token = refresh_access_token(mp_refresh, mp_secret)
    if not access_token:
        print("[ERRO] Falha ao obter token")
        return False
    print("[OK] Token obtido\n")

    # Carregar abril e maio
    print("[PASSO 2/3] Carregando dados de abril e maio...\n")
    resultados = []

    for mes, nome in [(4, "Abril 2026"), (5, "Maio 2026")]:
        linhas = carregar_mes(access_token, mes, nome)
        resultados.append((nome, linhas))

    # Resumo
    print(f"\n{'='*70}")
    print("RESUMO")
    print("="*70)
    for nome, linhas in resultados:
        print(f"{nome:<20} {linhas:6} linhas atualizadas")

    print("\n" + "="*70)
    print("[OK] CARREGAMENTO URGENTE CONCLUIDO")
    print("="*70 + "\n")

    return True


if __name__ == "__main__":
    sucesso = carregar_urgente()
    sys.exit(0 if sucesso else 1)

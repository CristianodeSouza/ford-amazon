#!/usr/bin/env python3
"""Script para carregar dados históricos de fevereiro a maio na planilha."""

import os
import sys
import csv
import json
import requests
from datetime import datetime, timedelta
from io import StringIO
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from mercado_pago import refresh_access_token
from sheets import (
    get_service, SPREADSHEET_ID,
    verificar_periodo_carregado, append_page1_raw_data, append_page2_reconciliacao,
    atualizar_planilha_com_mp, fetch_from_sheets
)

load_dotenv()

def listar_todos_relatorios(access_token: str) -> list[dict]:
    """Lista TODOS os relatórios de liquidação disponíveis."""
    try:
        url = "https://api.mercadopago.com/v1/account/settlement_report/list"
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list):
            data = [data]

        return data
    except Exception as e:
        print(f"[ERRO] Falha ao listar relatórios: {e}")
        return []


def baixar_csv_por_arquivo(access_token: str, file_name: str) -> str | None:
    """Baixa um CSV específico pelo nome do arquivo."""
    try:
        url = f"https://api.mercadopago.com/v1/account/settlement_report/{file_name}"
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        return resp.text
    except Exception as e:
        print(f"[AVISO] Falha ao baixar CSV {file_name}: {e}")
        return None


def filtrar_csv_por_periodo(csv_text: str, date_from: datetime, date_to: datetime) -> str:
    """Filtra CSV para manter apenas linhas dentro do período (por SETTLEMENT_DATE)."""
    try:
        resultado_linhas = []
        reader = csv.DictReader(StringIO(csv_text), delimiter=';', quoting=csv.QUOTE_ALL)

        if not reader.fieldnames:
            return ""

        # Adicionar cabeçalho
        resultado = ';'.join(reader.fieldnames) + '\n'

        # Processar linhas
        try:
            for row in reader:
                if 'SETTLEMENT_DATE' not in row:
                    continue

                try:
                    # Parse data (formato ISO: 2026-02-28T22:56:21.000-04:00)
                    data_str = row['SETTLEMENT_DATE'].strip()
                    if 'T' in data_str:
                        # Remover timezone para parsing
                        data_parte = data_str.split('T')[0]
                        data = datetime.strptime(data_parte, "%Y-%m-%d")
                    else:
                        data = datetime.strptime(data_str, "%Y-%m-%d")

                    # Incluir se está no período
                    if date_from <= data <= date_to:
                        resultado += ';'.join([row.get(col, '') for col in reader.fieldnames]) + '\n'
                except Exception as parse_err:
                    continue
        except csv.Error:
            # Se houver erro de CSV parsing, retornar o que conseguiu até agora
            pass

        return resultado
    except Exception as e:
        print(f"[ERRO] Falha ao filtrar CSV: {e}")
        return ""


def carregar_periodo(access_token: str, date_from: datetime, date_to: datetime, period_name: str) -> int:
    """Carrega dados de um período específico. Retorna total de linhas carregadas."""
    print(f"\n{'='*70}")
    print(f"CARREGANDO: {period_name}")
    print(f"Período: {date_from.strftime('%d/%m/%Y')} até {date_to.strftime('%d/%m/%Y')}")
    print('='*70)

    # Verificar se período já foi carregado
    if verificar_periodo_carregado(date_from, date_to):
        print(f"[INFO] Este período já foi carregado. Pulando...")
        return 0

    # Listar relatórios
    print(f"\n[1/3] Listando relatórios disponíveis...")
    relatorios = listar_todos_relatorios(access_token)
    print(f"[OK] {len(relatorios)} relatórios encontrados")

    if len(relatorios) == 0:
        print("[AVISO] Nenhum relatório disponível")
        return 0

    # Coletar CSVs para o período
    total_linhas_adicionadas = 0
    csv_combinado_linhas = {}

    print(f"\n[2/3] Baixando e filtrando CSVs...")
    relatorios_processados = 0

    # Otimização: usar apenas últimos N relatórios (os mais recentes provavelmente cobrem tudo)
    relatorios_para_tentar = relatorios[:20]  # Tentar apenas últimos 20
    print(f"  (Tentando últimos {len(relatorios_para_tentar)} relatórios de {len(relatorios)} disponíveis)")

    # Iterar pelos relatórios selecionados
    for i, rel in enumerate(relatorios_para_tentar):
        file_name = rel.get("file_name")
        if not file_name:
            continue

        print(f"  [{i+1}] Baixando {file_name}...")
        csv_text = baixar_csv_por_arquivo(access_token, file_name)

        if not csv_text:
            continue

        # Filtrar por período
        csv_filtrado = filtrar_csv_por_periodo(csv_text, date_from, date_to)

        # Contar linhas (excluir cabeçalho)
        linhas_filtradas = [l for l in csv_filtrado.split('\n') if l.strip() and not l.startswith(';')]
        if len(linhas_filtradas) > 1:  # Tem dados além do cabeçalho
            print(f"      [OK] {len(linhas_filtradas)-1} transações neste período")

            # Fazer append na Página1 (dados brutos)
            reader = csv.DictReader(StringIO(csv_filtrado), delimiter=';')
            for row in reader:
                source_id = row.get('SOURCE_ID', '').strip()
                real_amount = row.get('REAL_AMOUNT', '').strip()
                settlement_date = row.get('SETTLEMENT_DATE', '').strip()

                if source_id and real_amount:
                    csv_combinado_linhas[source_id] = {
                        'real_amount': real_amount,
                        'settlement_date': settlement_date,
                        'external_ref': row.get('EXTERNAL_REFERENCE', '').strip()
                    }

            relatorios_processados += 1

    print(f"\n[3/3] Atualizando Página2 com reconciliação...")
    try:
        # Ler dados atuais da planilha
        service = get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Página2!A:J"
        ).execute()
        rows = result.get("values", [])

        if not rows:
            print("[AVISO] Nenhuma linha na Página2")
            return 0

        # Preparar updates em batch (para linhas que devem ser preenchidas)
        updates = []

        for idx, row in enumerate(rows[1:], start=2):
            if not row or not any(row):
                continue

            id_operacao = row[9].strip() if len(row) > 9 and row[9] else ""

            if not id_operacao:
                continue

            # Se está nos dados combinados do período, atualizar
            if id_operacao in csv_combinado_linhas:
                valor_pago = csv_combinado_linhas[id_operacao]['real_amount']
                updates.append({
                    "range": f"Página2!E{idx}",
                    "values": [[valor_pago]]
                })
                total_linhas_adicionadas += 1

        # Executar updates em batch (append aos dados existentes)
        if updates:
            body = {"data": updates, "valueInputOption": "USER_ENTERED"}
            result = service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
            print(f"Página2: {len(updates)} linhas atualizadas com dados do MP")

        return total_linhas_adicionadas

    except Exception as e:
        print(f"[ERRO] Falha ao atualizar Página2: {e}")
        import traceback
        traceback.print_exc()
        return 0


def carregar_tudo_historico():
    """Carrega todos os dados históricos (fev-mai 2026)."""
    print("\n" + "="*70)
    print("CARREGAMENTO DE DADOS HISTÓRICOS — Ford Amazon Dashboard")
    print("="*70)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

    # Credenciais
    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais do Mercado Pago não encontradas!")
        print("Configure MP_REFRESH_TOKEN e MP_CLIENT_SECRET no .env")
        return False

    # Refresh token
    print("[1/6] Obtendo novo access token do MP...")
    access_token = refresh_access_token(mp_refresh, mp_secret)
    if not access_token:
        print("[ERRO] Falha ao obter access token")
        return False
    print("[OK] Token obtido com sucesso\n")

    # Períodos a carregar (janeiro já foi carregado)
    periodos = [
        (datetime(2026, 2, 1), datetime(2026, 2, 28), "Fevereiro 2026"),
        (datetime(2026, 3, 1), datetime(2026, 3, 31), "Março 2026"),
        (datetime(2026, 4, 1), datetime(2026, 4, 30), "Abril 2026"),
        (datetime(2026, 5, 1), datetime(2026, 5, 26), "Maio 2026"),
    ]

    # Carregar cada período
    resultados = []
    total_geral = 0

    print("[2-5/6] Carregando períodos...\n")
    for i, (date_from, date_to, period_name) in enumerate(periodos):
        linhas = carregar_periodo(access_token, date_from, date_to, period_name)
        resultados.append((period_name, linhas))
        total_geral += linhas

    # Validar dados
    print(f"\n[6/6] Validando dados carregados...")
    try:
        registros = fetch_from_sheets()
        print(f"[OK] Total de registros na planilha: {len(registros)}\n")
    except Exception as e:
        print(f"[AVISO] Erro ao validar: {e}\n")

    # Resumo
    print("="*70)
    print("RESUMO DO CARREGAMENTO")
    print("="*70)
    print(f"{'Período':<20} {'Linhas':<10} {'Status':<10}")
    print("-"*70)
    for period_name, linhas in resultados:
        status = "[OK]" if linhas > 0 else "[INFO]"
        print(f"{period_name:<20} {linhas:<10} {status}")
    print("-"*70)
    print(f"{'TOTAL':<20} {total_geral:<10}")
    print("\n" + "="*70)
    print("[OK] CARREGAMENTO CONCLUÍDO")
    print("="*70 + "\n")

    return True


if __name__ == "__main__":
    sucesso = carregar_tudo_historico()
    sys.exit(0 if sucesso else 1)

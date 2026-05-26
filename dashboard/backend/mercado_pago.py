import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

MP_CLIENT_ID = "3857722102307647"
MP_USER_ID = 1576552143
ML_CLIENT_ID = "3857722102307647"
ML_USER_ID = 1576552143

def refresh_access_token(refresh_token: str, client_secret: str) -> str | None:
    """Obtém novo access_token usando refresh_token."""
    try:
        url = "https://api.mercadopago.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": MP_CLIENT_ID,
            "client_secret": client_secret,
            "refresh_token": refresh_token
        }
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Erro ao refresh MP token: {e}")
        return None


def buscar_pagamentos_90_dias(access_token: str) -> list[dict]:
    """Busca pagamentos aprovados dos últimos 90 dias."""
    try:
        # Calcular intervalo: últimos 90 dias
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

        begin_date = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59Z")

        url = "https://api.mercadopago.com/v1/payments/search"
        headers = {"Authorization": f"Bearer {access_token}"}

        all_payments = []
        offset = 0

        while True:
            params = {
                "range": "date_created",
                "begin_date": begin_date,
                "end_date": end_date_str,
                "status": "approved",
                "sort": "date_created",
                "criteria": "desc",
                "offset": offset,
                "limit": 50
            }

            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            if not results:
                break

            all_payments.extend(results)

            paging = data.get("paging", {})
            if len(all_payments) >= paging.get("total", 0):
                break

            offset += 50

        return all_payments
    except Exception as e:
        print(f"Erro ao buscar pagamentos MP: {e}")
        return []


def extrair_dados_pagamento(payment: dict) -> dict:
    """Extrai campos relevantes de um pagamento do MP."""
    return {
        "id_operacao": payment.get("id"),
        "external_reference": payment.get("external_reference"),
        "valor_pago_mp": payment.get("transaction_amount"),
        "valor_liquido": payment.get("net_received_amount"),
        "status": payment.get("status"),
        "data_aprovacao": payment.get("date_approved"),
        "data_criacao": payment.get("date_created"),
        "metodo_pagamento": payment.get("payment_method_id"),
    }


def buscar_pagamentos_por_nf(access_token: str, nf: str) -> dict | None:
    """Busca um pagamento específico pelo external_reference (NF)."""
    try:
        url = "https://api.mercadopago.com/v1/payments/search"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "external_reference": str(nf).strip(),
            "status": "approved"
        }

        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if results:
            return extrair_dados_pagamento(results[0])
        return None
    except Exception as e:
        print(f"Erro ao buscar pagamento para NF {nf}: {e}")
        return None


def criar_mapa_pagamentos_por_nf(access_token: str) -> dict:
    """Cria um dicionário {external_reference: dados_pagamento} para todos os pagamentos."""
    try:
        pagamentos = buscar_pagamentos_90_dias(access_token)
        mapa = {}
        for pag in pagamentos:
            external_ref = pag.get("external_reference")
            if external_ref:
                mapa[str(external_ref).strip()] = extrair_dados_pagamento(pag)
        return mapa
    except Exception as e:
        print(f"Erro ao criar mapa de pagamentos: {e}")
        return {}


def refresh_ml_access_token(refresh_token: str, client_secret: str) -> str | None:
    """Obtém novo access_token para Mercado Livre usando refresh_token."""
    try:
        url = "https://api.mercadolibre.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": ML_CLIENT_ID,
            "client_secret": client_secret,
            "refresh_token": refresh_token
        }
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"Erro ao refresh ML token: {e}")
        return None


def buscar_pedidos_ml(access_token: str) -> list[dict]:
    """Busca pedidos do usuário no Mercado Livre."""
    try:
        url = f"https://api.mercadolibre.com/orders/search/seller/{ML_USER_ID}"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "sort": "date_created",
            "order": "desc",
            "limit": 100
        }

        all_orders = []
        offset = 0

        while True:
            params["offset"] = offset
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            orders = data.get("orders", [])
            if not orders:
                break

            all_orders.extend(orders)

            paging = data.get("paging", {})
            if len(all_orders) >= paging.get("total", 0):
                break

            offset += 100

        return all_orders
    except Exception as e:
        print(f"Erro ao buscar pedidos ML: {e}")
        return []


def buscar_nf_por_order_id(access_token_ml: str, order_id: str) -> dict | None:
    """Busca a NF de um pedido no ML usando o order_id."""
    try:
        url = f"https://api.mercadolibre.com/users/{ML_USER_ID}/invoices/orders/{order_id}"
        headers = {"Authorization": f"Bearer {access_token_ml}"}

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        data = resp.json()
        return {
            "invoice_number": data.get("invoice_number"),
            "issued_date": data.get("issued_date"),
            "recipient_name": data.get("recipient", {}).get("name", ""),
            "amount": data.get("amount"),
        }
    except Exception as e:
        print(f"Erro ao buscar NF para order_id {order_id}: {e}")
        return None


def baixar_csv_liquidacao_mp(access_token: str) -> str | None:
    """Baixa o CSV de liquidação mais recente do MP."""
    try:
        # Primeiro, listar os relatórios de liquidação disponíveis
        url = "https://api.mercadopago.com/v1/account/settlement-report/list"
        headers = {"Authorization": f"Bearer {access_token}"}

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        data = resp.json()
        if not isinstance(data, list):
            data = [data]

        if not data:
            print("Nenhum relatório de liquidação disponível")
            return None

        # Pegar o mais recente
        mais_recente = data[-1]
        filename = mais_recente.get("file_name")

        if not filename:
            print("Nenhum arquivo encontrado no relatório")
            return None

        # Baixar o arquivo CSV
        url_csv = f"https://api.mercadopago.com/v1/account/settlement-report/{filename}"
        resp = requests.get(url_csv, headers=headers, timeout=30)
        resp.raise_for_status()

        return resp.text
    except Exception as e:
        print(f"Erro ao baixar CSV de liquidação: {e}")
        return None

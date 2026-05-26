#!/usr/bin/env python3
"""Verifica permissões de API do Mercado Pago."""

import os
import sys
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'dashboard', 'backend'))

from mercado_pago import refresh_access_token

load_dotenv()

def verificar_permissoes():
    """Verifica permissões da aplicação."""
    print("\n" + "="*70)
    print("VERIFICAÇÃO DE PERMISSÕES - Mercado Pago API")
    print("="*70 + "\n")

    mp_refresh = os.environ.get("MP_REFRESH_TOKEN")
    mp_secret = os.environ.get("MP_CLIENT_SECRET")
    app_id = os.environ.get("MP_APP_ID")

    if not mp_refresh or not mp_secret:
        print("[ERRO] Credenciais não encontradas")
        return False

    print("[1/3] Obtendo access token...")
    access_token = refresh_access_token(mp_refresh, mp_secret)
    if not access_token:
        print("[ERRO] Falha ao obter token")
        return False
    print("[OK] Token obtido\n")

    # Verificar informações da conta
    print("[2/3] Obtendo informações da conta...\n")

    try:
        headers = {"Authorization": f"Bearer {access_token}"}

        # GET /v1/users/me
        resp = requests.get("https://api.mercadopago.com/v1/users/me",
                          headers=headers, timeout=10)
        resp.raise_for_status()
        user_data = resp.json()

        print(f"Usuário ID: {user_data.get('id')}")
        print(f"Email: {user_data.get('email')}")
        print(f"País: {user_data.get('country_id')}")
        print(f"Tipo: {user_data.get('user_type')}")

        if 'account' in user_data:
            print(f"Status Conta: {user_data['account'].get('status')}")

    except Exception as e:
        print(f"[AVISO] Não foi possível obter info da conta: {e}\n")

    # Verificar aplicação
    print(f"\n[3/3] Verificando aplicação e permissões...\n")

    try:
        # Lista aplicações
        resp = requests.get("https://api.mercadopago.com/v1/applications",
                          headers=headers, timeout=10)
        resp.raise_for_status()
        apps = resp.json()

        print(f"Aplicações registradas: {len(apps)}\n")

        for app in apps:
            app_id = app.get('id')
            app_name = app.get('name')
            print(f"  ID: {app_id}")
            print(f"  Nome: {app_name}")
            print(f"  Status: {app.get('status')}")

            # Tentar obter permissões da app
            try:
                resp_perms = requests.get(
                    f"https://api.mercadopago.com/v1/applications/{app_id}/permissions",
                    headers=headers, timeout=10
                )
                if resp_perms.ok:
                    perms = resp_perms.json()
                    if isinstance(perms, list):
                        print(f"  Permissões: {len(perms)}")
                        # Procura por settlement
                        settlement_perms = [p for p in perms if 'settlement' in str(p).lower()]
                        if settlement_perms:
                            print(f"    Settlement: {settlement_perms}")
                    elif isinstance(perms, dict):
                        settlement_keys = [k for k in perms.keys() if 'settlement' in k.lower()]
                        if settlement_keys:
                            print(f"    Settlement permissions found: {settlement_keys}")
                            for key in settlement_keys:
                                print(f"      {key}: {perms[key]}")
            except:
                pass

            print()

    except Exception as e:
        print(f"[AVISO] Erro ao verificar aplicações: {e}\n")

    # Testar endpoints de settlement
    print("\nTestando acesso aos endpoints de settlement:\n")

    endpoints = [
        ("GET /list", "https://api.mercadopago.com/v1/account/settlement_report/list", "get"),
        ("POST /create", "https://api.mercadopago.com/v1/account/settlement-report", "post"),
    ]

    for desc, url, method in endpoints:
        try:
            if method == "get":
                resp = requests.get(url, headers=headers, timeout=10)
            else:
                data = {
                    "begin_date": "2026-04-01T00:00:00Z",
                    "end_date": "2026-04-30T23:59:59Z"
                }
                headers["Content-Type"] = "application/json"
                resp = requests.post(url, headers=headers, json=data, timeout=10)

            status = resp.status_code
            if status == 200:
                symbol = "OK"
            elif status == 404:
                symbol = "NO"
            else:
                symbol = "?"

            print(f"  [{symbol}] {desc:20} Status: {status}")

            if status >= 400:
                error = resp.json() if resp.ok == False else {}
                if 'message' in error:
                    print(f"       Erro: {error['message']}")
        except Exception as e:
            print(f"  [NO] {desc:20} Erro: {str(e)[:60]}")

    print("\n" + "="*70)
    print("CONCLUSÃO:")
    print("="*70)
    print("""
Se POST /create retorna 404: Seu app pode não ter permissão.

Solução:
1. Acesse: https://www.mercadopago.com.br/business/account/apps
2. Clique em sua aplicação
3. Vá em "Configurações avançadas" ou "Scopes"
4. Procure por "Settlement Reports" ou "Relatórios de Liquidação"
5. Ative a permissão se disponível
6. Salve e regenere as credenciais se necessário

Alternativa:
- Gere os relatórios manualmente via dashboard MP
- O script carregará automaticamente quando disponíveis
""")
    print("="*70 + "\n")

    return True

if __name__ == "__main__":
    sucesso = verificar_permissoes()
    sys.exit(0 if sucesso else 1)

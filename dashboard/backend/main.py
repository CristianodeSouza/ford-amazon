import os
import re
import logging
from collections import defaultdict
from datetime import date, datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sheets import fetch_conciliacao, atualizar_planilha_com_mp
from mercado_pago import refresh_access_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ford Amazon — Conciliação Dashboard")

# Scheduler para atualização automática diária
scheduler = BackgroundScheduler()

def job_atualizar_dados():
    """Job que executa diariamente para atualizar dados da planilha."""
    try:
        logger.info(f"[{datetime.now()}] Iniciando atualização automática...")

        # Tentar atualizar planilha com dados do MP
        mp_refresh_token = os.environ.get("MP_REFRESH_TOKEN")
        mp_client_secret = os.environ.get("MP_CLIENT_SECRET")

        if mp_refresh_token and mp_client_secret:
            try:
                token = refresh_access_token(mp_refresh_token, mp_client_secret)
                if token:
                    linhas = atualizar_planilha_com_mp(token)
                    logger.info(f"[{datetime.now()}] Planilha atualizada com {linhas} pagamentos do MP")
            except Exception as e:
                logger.warning(f"[{datetime.now()}] Erro ao atualizar com MP (continuando): {str(e)}")

        # Sempre buscar dados (para cache)
        fetch_conciliacao()
        logger.info(f"[{datetime.now()}] Atualização automática concluída!")
    except Exception as e:
        logger.error(f"[{datetime.now()}] Erro na atualização automática: {str(e)}")

# Agendar job para rodar todo dia às 09:00 (horário do servidor)
scheduler.add_job(job_atualizar_dados, 'cron', hour=9, minute=0, id='atualizar_dados_diario')
scheduler.start()
logger.info("Scheduler iniciado - atualização automática às 09:00 UTC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Em produção (Render), busca em ../.., em dev usa ../frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/css",    StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js",     StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")),  name="js")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/conciliacao")
def listar_conciliacao(
    nota_fiscal: str = Query(None),
    cliente: str = Query(None),
    id_operacao: str = Query(None),
    tipo: str = Query(None),        # "normal" | "disputa" | None = todos
    data_inicio: str = Query(None), # YYYY-MM-DD
    data_fim: str = Query(None),    # YYYY-MM-DD
):
    try:
        registros = fetch_conciliacao()
    except Exception as e:
        return {"total": 0, "registros": [], "totais": {}, "resumo": {}, "aviso": f"Erro ao ler planilha: {str(e)}"}

    # Filtro textual por NF (quando ativo, ignora datas — busca em todo o histórico)
    nf_buscada = bool(nota_fiscal and nota_fiscal.strip())
    if nf_buscada:
        t = nota_fiscal.strip().lower()
        registros = [r for r in registros if t in str(r["nota_fiscal"]).lower()]

    # Filtro por cliente
    if cliente and cliente.strip():
        t = cliente.strip().lower()
        registros = [r for r in registros if t in str(r["cliente"]).lower()]

    # Filtro por ID da Operação / Source ID
    if id_operacao and id_operacao.strip():
        t = id_operacao.strip().lower()
        registros = [r for r in registros if t in str(r["id_operacao"]).lower()]

    # Filtro de período — ignorado quando a busca é por NF específica
    if not nf_buscada and (data_inicio or data_fim):
        registros = _filtrar_por_data(registros, data_inicio, data_fim)

    # Resumo ANTES de filtrar por tipo (para os cards sempre mostrarem os totais globais)
    normais   = [r for r in registros if r["tipo"] == "normal"]
    disputas  = [r for r in registros if r["tipo"] == "disputa"]

    def soma_nf(lista):
        return round(sum(r["valor_nf"] or 0 for r in lista), 2)
    def soma_pago(lista):
        return round(sum(r["valor_pago_mp"] or 0 for r in lista), 2)

    resumo = {
        "total":            len(registros),
        "total_normais":    len(normais),
        "total_disputas":   len(disputas),
        "nf_normais":       soma_nf(normais),
        "pago_normais":     soma_pago(normais),
        "diff_normais":     round(soma_nf(normais) - soma_pago(normais), 2),
        "nf_disputas":      soma_nf(disputas),
        "pago_disputas":    soma_pago(disputas),   # será negativo
        "nf_total":         soma_nf(registros),
        "pago_total":       soma_pago(registros),
        "diff_total":       round(soma_nf(registros) - soma_pago(registros), 2),
    }

    # Filtra por tipo para a tabela
    if tipo in ("normal", "disputa"):
        registros = [r for r in registros if r["tipo"] == tipo]

    return {
        "total":     len(registros),
        "registros": registros,
        "resumo":    resumo,
    }


@app.post("/api/refresh")
def refresh_dados():
    """Força atualização imediata dos dados da planilha."""
    try:
        logger.info(f"[{datetime.now()}] Refresh manual solicitado")

        # Tentar atualizar planilha com dados do MP
        mp_refresh_token = os.environ.get("MP_REFRESH_TOKEN")
        mp_client_secret = os.environ.get("MP_CLIENT_SECRET")
        linhas_mp = 0

        if mp_refresh_token and mp_client_secret:
            try:
                token = refresh_access_token(mp_refresh_token, mp_client_secret)
                if token:
                    linhas_mp = atualizar_planilha_com_mp(token)
                    logger.info(f"[{datetime.now()}] Planilha atualizada com {linhas_mp} pagamentos do MP")
            except Exception as e:
                logger.warning(f"[{datetime.now()}] Erro ao atualizar com MP (continuando): {str(e)}")

        # Sempre buscar dados (para cache)
        registros = fetch_conciliacao()
        logger.info(f"[{datetime.now()}] Refresh manual concluído - {len(registros)} registros")

        return {
            "message": "Dados atualizados",
            "total": len(registros),
            "linhas_atualizadas_mp": linhas_mp,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erro no refresh: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
def status():
    """Status da aplicação e próxima atualização agendada."""
    next_run = scheduler.get_job('atualizar_dados_diario')
    return {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "next_scheduled_update": next_run.next_run_time.isoformat() if next_run else None,
        "scheduler_running": scheduler.running
    }


# ── HELPERS CONCILIAÇÃO ────────────────────────────────────────────────────────

def _parse_data_venda(data_str: str):
    """Converte DD/MM/AAAA ou AAAA-MM-DD para date. Retorna None se inválido."""
    s = str(data_str or "").strip()
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    m2 = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m2:
        try:
            return date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError:
            return None
    return None


def _filtrar_por_data(registros: list, data_inicio: str | None, data_fim: str | None) -> list:
    """Filtra registros pelo campo data_venda dentro do intervalo [data_inicio, data_fim]."""
    if not data_inicio and not data_fim:
        return registros
    try:
        dt_ini = date.fromisoformat(data_inicio) if data_inicio else None
        dt_fim = date.fromisoformat(data_fim)    if data_fim    else None
    except ValueError:
        return registros
    resultado = []
    for r in registros:
        dt = _parse_data_venda(r.get("data_venda") or "")
        if dt is None:
            continue
        if dt_ini and dt < dt_ini:
            continue
        if dt_fim and dt > dt_fim:
            continue
        resultado.append(r)
    return resultado


def _classificar(r: dict) -> str:
    if r.get("valor_nf") is None or r.get("valor_pago_mp") is None:
        return "sem_dados"
    if r.get("tipo") == "disputa":
        return "disputa"
    d = r.get("diferenca")
    if d is not None and abs(d) <= 0.01:
        return "ok"
    return "divergente"


def _mes_chave(data_str: str) -> str | None:
    if not data_str:
        return None
    # Tenta DD/MM/AAAA
    m = re.search(r'(\d{1,2})/(\d{4})', data_str)
    if m:
        mes, ano = int(m.group(1)), m.group(2)
    else:
        # Tenta AAAA-MM (ISO)
        m2 = re.search(r'(\d{4})-(\d{2})', data_str)
        if m2:
            mes, ano = int(m2.group(2)), m2.group(1)
        else:
            return None
    nomes = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    try:
        return f"{nomes[mes]}/{ano[2:]}"
    except (IndexError, ValueError):
        return None


@app.get("/api/indicadores")
def get_indicadores(
    data_inicio: str = Query(None),
    data_fim: str = Query(None),
    nota_fiscal: str = Query(None),
    cliente: str = Query(None),
    id_operacao: str = Query(None),
):
    try:
        registros = fetch_conciliacao()
    except Exception as e:
        return {"erro": str(e)}

    if data_inicio or data_fim:
        registros = _filtrar_por_data(registros, data_inicio, data_fim)

    if nota_fiscal and nota_fiscal.strip():
        t = nota_fiscal.strip().lower()
        registros = [r for r in registros if t in str(r["nota_fiscal"]).lower()]
    if cliente and cliente.strip():
        t = cliente.strip().lower()
        registros = [r for r in registros if t in str(r["cliente"]).lower()]
    if id_operacao and id_operacao.strip():
        t = id_operacao.strip().lower()
        registros = [r for r in registros if t in str(r["id_operacao"]).lower()]

    for r in registros:
        r["status"] = _classificar(r)

    normais  = [r for r in registros if r["tipo"] == "normal"]
    disputas = [r for r in registros if r["tipo"] == "disputa"]

    total_ok  = sum(1 for r in normais if r["status"] == "ok")
    total_div = sum(1 for r in normais if r["status"] == "divergente")
    total_sem = sum(1 for r in registros if r["status"] == "sem_dados")
    total_dis = len(disputas)
    base = total_ok + total_div + total_sem
    taxa = round(total_ok / base * 100, 1) if base > 0 else 0.0

    val_fat = round(sum(r["valor_nf"] or 0 for r in normais), 2)
    val_rec = round(sum(r["valor_pago_mp"] or 0 for r in normais), 2)
    val_tax = round(val_fat - val_rec, 2)
    val_dis = round(sum(abs(r["valor_pago_mp"] or 0) for r in disputas), 2)
    saldo   = round(val_rec - val_dis, 2)

    mensal: dict = defaultdict(lambda: {"faturado": 0.0, "recebido": 0.0})
    for r in normais:
        k = _mes_chave(r.get("data_venda") or "")
        if k:
            mensal[k]["faturado"] += r["valor_nf"] or 0
            mensal[k]["recebido"] += r["valor_pago_mp"] or 0

    _ord = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6,
            "Jul": 7, "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12}

    def _sk(k: str):
        p = k.split("/")
        return (int(p[1]) if len(p) > 1 and p[1].isdigit() else 0, _ord.get(p[0], 0))

    evolucao = [
        {"mes": k, "faturado": round(v["faturado"], 2), "recebido": round(v["recebido"], 2)}
        for k, v in sorted(mensal.items(), key=lambda x: _sk(x[0]))
    ]

    divs_sorted = sorted(
        [r for r in registros if r["status"] == "divergente"],
        key=lambda r: abs(r.get("diferenca") or 0),
        reverse=True
    )[:10]

    top_div = [
        {
            "nota_fiscal": r["nota_fiscal"],
            "cliente": r.get("cliente", ""),
            "diferenca": r.get("diferenca"),
            "valor_nf": r.get("valor_nf"),
            "valor_pago_mp": r.get("valor_pago_mp"),
        }
        for r in divs_sorted
    ]

    pct_tax = round(val_tax / val_fat * 100, 1) if val_fat else 0.0
    pct_dis = round(val_dis / val_fat * 100, 1) if val_fat else 0.0
    pct_rec = round(val_rec / val_fat * 100, 1) if val_fat else 0.0

    return {
        "taxa_conciliacao": taxa,
        "total_ok": total_ok,
        "total_divergente": total_div,
        "total_disputa": total_dis,
        "total_sem_dados": total_sem,
        "valor_faturado": val_fat,
        "valor_recebido": val_rec,
        "valor_taxas": val_tax,
        "valor_disputas": val_dis,
        "saldo_liquido": saldo,
        "pct_taxas": pct_tax,
        "pct_disputas": pct_dis,
        "pct_recebido": pct_rec,
        "evolucao_mensal": evolucao,
        "top_divergencias": top_div,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

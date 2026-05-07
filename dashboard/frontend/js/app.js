// ── Instâncias Chart.js (fora do Alpine para evitar reatividade) ───────────────
let _chartStatus = null;
let _chartMensal = null;
let _chartTopDiv = null;

// ── Alpine.js — componente principal ──────────────────────────────────────────
function dashboard() {
  return {
    registros: [],
    resumo: {
      total: 0, total_normais: 0, total_disputas: 0,
      nf_normais: 0, pago_normais: 0, diff_normais: 0,
      nf_disputas: 0, pago_disputas: 0,
      nf_total: 0, pago_total: 0, diff_total: 0,
    },
    ind: {
      taxa_conciliacao: 0.0,
      total_ok: 0, total_divergente: 0, total_disputa: 0, total_sem_dados: 0,
      valor_faturado: 0, valor_recebido: 0,
      valor_taxas: 0, valor_disputas: 0, saldo_liquido: 0,
      pct_taxas: 0, pct_disputas: 0, pct_recebido: 0,
      evolucao_mensal: [],
      top_divergencias: [],
    },
    total: 0,
    aba: 'todos',
    buscaNF: '',
    buscaCliente: '',
    dataInicio: '',
    dataFim: '',
    loading: true,
    loadingInd: true,
    aviso: null,
    ultimaAtualizacao: null,

    // ── Init ────────────────────────────────────────────────────────────────────
    async init() {
      await Promise.all([this.carregar(), this.carregarIndicadores()]);
    },

    // ── Params de data (só quando não há busca por NF) ─────────────────────────
    _dateParams() {
      const p = new URLSearchParams();
      if (!this.buscaNF.trim()) {
        if (this.dataInicio) p.append('data_inicio', this.dataInicio);
        if (this.dataFim)    p.append('data_fim',    this.dataFim);
      }
      return p;
    },

    // ── Carregar tabela ─────────────────────────────────────────────────────────
    async carregar() {
      this.loading = true;
      this.aviso = null;
      try {
        const params = this._dateParams();
        if (this.buscaNF.trim())      params.append('nota_fiscal', this.buscaNF.trim());
        if (this.buscaCliente.trim()) params.append('cliente',     this.buscaCliente.trim());
        if (this.aba !== 'todos')     params.append('tipo',        this.aba);

        const res = await fetch('/api/conciliacao?' + params.toString());
        if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);
        const data = await res.json();

        this.registros = data.registros || [];
        this.resumo    = data.resumo    || this.resumo;
        this.total     = data.total     || 0;
        this.aviso     = data.aviso     || null;

        const agora = new Date();
        this.ultimaAtualizacao = agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        this.aviso = 'Nao foi possivel carregar os dados: ' + e.message;
      } finally {
        this.loading = false;
      }
    },

    // ── Carregar indicadores ────────────────────────────────────────────────────
    async carregarIndicadores() {
      this.loadingInd = true;
      try {
        const params = this._dateParams();
        const res = await fetch('/api/indicadores?' + params.toString());
        if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);
        const data = await res.json();
        if (data.erro) return;
        Object.assign(this.ind, data);
        await this.$nextTick();
        inicializarGraficos(this.ind);
      } catch (e) {
        console.warn('Indicadores:', e.message);
      } finally {
        this.loadingInd = false;
      }
    },

    // ── Aplicar todos os filtros (tabela + indicadores) ─────────────────────────
    async aplicarFiltros() {
      await Promise.all([this.carregar(), this.carregarIndicadores()]);
    },

    // ── Limpar todos os filtros ────────────────────────────────────────────────
    limparFiltros() {
      this.buscaNF      = '';
      this.buscaCliente = '';
      this.dataInicio   = '';
      this.dataFim      = '';
      this.aplicarFiltros();
    },

    // ── Atalhos de período ─────────────────────────────────────────────────────
    setPreset(tipo) {
      const hoje = new Date();
      const iso  = d => d.toISOString().slice(0, 10);
      const mm   = n => String(n).padStart(2, '0');

      if (tipo === 'hoje') {
        this.dataInicio = iso(hoje);
        this.dataFim    = iso(hoje);
      } else if (tipo === 'mes') {
        this.dataInicio = `${hoje.getFullYear()}-${mm(hoje.getMonth() + 1)}-01`;
        this.dataFim    = iso(hoje);
      } else if (tipo === 'mes_ant') {
        const primeiro = new Date(hoje.getFullYear(), hoje.getMonth() - 1, 1);
        const ultimo   = new Date(hoje.getFullYear(), hoje.getMonth(), 0);
        this.dataInicio = iso(primeiro);
        this.dataFim    = iso(ultimo);
      } else if (tipo === 'ano') {
        this.dataInicio = `${hoje.getFullYear()}-01-01`;
        this.dataFim    = iso(hoje);
      }
      this.aplicarFiltros();
    },

    // ── Label do período ativo ─────────────────────────────────────────────────
    labelPeriodo() {
      const fmt = d => d ? new Date(d + 'T12:00:00').toLocaleDateString('pt-BR') : null;
      const ini = fmt(this.dataInicio);
      const fim = fmt(this.dataFim);
      if (ini && fim) return `${ini} a ${fim}`;
      if (ini)        return `A partir de ${ini}`;
      if (fim)        return `Ate ${fim}`;
      return '';
    },

    // ── Atualizar tudo ──────────────────────────────────────────────────────────
    async atualizar() {
      this.loading    = true;
      this.loadingInd = true;
      this.aviso      = null;
      try {
        await fetch('/api/refresh', { method: 'POST' });
        await this.aplicarFiltros();
      } catch (e) {
        this.aviso      = 'Erro ao atualizar: ' + e.message;
        this.loading    = false;
        this.loadingInd = false;
      }
    },

    // ── Formatadores ────────────────────────────────────────────────────────────
    fmt(value) {
      if (value == null || value === '') return '—';
      return new Intl.NumberFormat('pt-BR', {
        style: 'currency', currency: 'BRL', minimumFractionDigits: 2,
      }).format(value);
    },

    pct(parte, total) {
      if (!total || total === 0) return '—';
      return (Math.abs(parte / total) * 100).toFixed(1) + '%';
    },

    // ── Status de cada registro ─────────────────────────────────────────────────
    statusReg(r) {
      if (r.valor_nf == null || r.valor_pago_mp == null) return 'sem_dados';
      if (r.tipo === 'disputa') return 'disputa';
      const d = r.diferenca;
      if (d != null && Math.abs(d) <= 0.01) return 'ok';
      return 'divergente';
    },

    statusLabel(r) {
      return { ok: 'Conciliada', divergente: 'Divergente', disputa: 'Disputa', sem_dados: 'Sem Dados' }[this.statusReg(r)] || '—';
    },

    statusBadgeClass(r) {
      return { ok: 'sbadge-ok', divergente: 'sbadge-div', disputa: 'sbadge-disp', sem_dados: 'sbadge-sem' }[this.statusReg(r)] || '';
    },

    // ── Ação recomendada por linha ──────────────────────────────────────────────
    acaoTag(r) {
      const s = this.statusReg(r);
      if (s === 'ok')         return 'Arquivar';
      if (s === 'disputa')    return 'Contestar';
      if (s === 'sem_dados')  return 'Investigar';
      if (s === 'divergente') return r.diferenca > 0 ? 'Checar taxa' : 'Checar NF';
      return '—';
    },

    acaoTagClass(r) {
      return { ok: 'atag-ok', divergente: 'atag-div', disputa: 'atag-disp', sem_dados: 'atag-sem' }[this.statusReg(r)] || '';
    },

    // ── Classes da tabela ───────────────────────────────────────────────────────
    rowClass(r, i) {
      if (r.tipo === 'disputa') return 'tr-disputa';
      const s = this.statusReg(r);
      if (s === 'divergente') return i % 2 === 0 ? 'tr-divergente-even' : 'tr-divergente-odd';
      return i % 2 === 0 ? 'tr-even' : 'tr-odd';
    },

    diffClass(r) {
      if (r.tipo === 'disputa') return 'diff-disputa';
      const d = r.diferenca;
      if (d == null)           return '';
      if (Math.abs(d) <= 0.01) return 'diff-ok';
      if (d > 0.01)            return 'diff-normal';
      return 'diff-alert';
    },

    abaLabel() {
      if (this.aba === 'normal')  return 'Transacoes Normais';
      if (this.aba === 'disputa') return 'Disputas / Chargebacks';
      return 'Todos os registros';
    },
  };
}

// ── Chart.js — funções externas (sem reatividade Alpine) ──────────────────────

const CORES = {
  ok: '#16a34a', div: '#d97706', disp: '#dc2626', sem: '#94a3b8',
  ford: '#003087', fordMid: '#0050d0', green: '#16a34a',
};

const CHART_FONT = { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", size: 11 };
const CHART_COLOR = '#64748b';

function fmtBRL(v) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2 }).format(v);
}

function inicializarGraficos(ind) {
  buildChartStatus(ind);
  buildChartMensal(ind);
  buildChartTopDiv(ind);
}

// ── Gráfico 1: Donut — Status ─────────────────────────────────────────────────
function buildChartStatus(ind) {
  const ctx = document.getElementById('chartStatus');
  if (!ctx) return;
  if (_chartStatus) { _chartStatus.destroy(); _chartStatus = null; }

  const total = (ind.total_ok || 0) + (ind.total_divergente || 0) +
                (ind.total_disputa || 0) + (ind.total_sem_dados || 0);

  _chartStatus = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Conciliadas', 'Divergentes', 'Disputas', 'Sem Dados'],
      datasets: [{
        data: [ind.total_ok || 0, ind.total_divergente || 0, ind.total_disputa || 0, ind.total_sem_dados || 0],
        backgroundColor: [CORES.ok, CORES.div, CORES.disp, CORES.sem],
        borderWidth: 3, borderColor: '#ffffff', hoverOffset: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '72%',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) {
              const v = ctx.parsed;
              const pct = total > 0 ? ((v / total) * 100).toFixed(1) : 0;
              return ` ${v} NF(s) — ${pct}%`;
            },
          },
        },
      },
    },
  });
}

// ── Gráfico 2: Barras — Evolução Mensal ──────────────────────────────────────
function buildChartMensal(ind) {
  const ctx = document.getElementById('chartMensal');
  if (!ctx) return;
  if (_chartMensal) { _chartMensal.destroy(); _chartMensal = null; }

  const dados = ind.evolucao_mensal || [];
  if (dados.length === 0) return;

  _chartMensal = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: dados.map(d => d.mes),
      datasets: [
        {
          label: 'Faturado (NF)',
          data: dados.map(d => d.faturado),
          backgroundColor: 'rgba(0,48,135,0.80)', borderColor: CORES.ford,
          borderWidth: 1, borderRadius: 4,
        },
        {
          label: 'Recebido (MP)',
          data: dados.map(d => d.recebido),
          backgroundColor: 'rgba(22,163,74,0.75)', borderColor: CORES.green,
          borderWidth: 1, borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) { return ` ${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}`; },
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: CHART_FONT, color: CHART_COLOR } },
        y: {
          beginAtZero: true, grid: { color: '#f1f5f9' },
          ticks: {
            font: CHART_FONT, color: CHART_COLOR,
            callback(v) { return v >= 1000 ? 'R$' + (v / 1000).toFixed(0) + 'k' : 'R$' + v; },
          },
        },
      },
    },
  });
}

// ── Gráfico 3: Barras horizontais — Top Divergências ─────────────────────────
function buildChartTopDiv(ind) {
  const ctx = document.getElementById('chartTopDiv');
  if (!ctx) return;
  if (_chartTopDiv) { _chartTopDiv.destroy(); _chartTopDiv = null; }

  const dados = (ind.top_divergencias || []).slice().reverse();
  if (dados.length === 0) return;

  const labels = dados.map(d => {
    const nf = d.nota_fiscal || '—';
    return nf.length > 10 ? nf.slice(0, 10) + '…' : nf;
  });

  _chartTopDiv = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Diferença (R$)',
        data: dados.map(d => Math.abs(d.diferenca || 0)),
        backgroundColor: dados.map(d => (d.diferenca || 0) > 0 ? CORES.div : CORES.disp),
        borderWidth: 0, borderRadius: 3,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title(items) { return `NF: ${dados[items[0].dataIndex].nota_fiscal}`; },
            label(ctx) {
              const d = dados[ctx.dataIndex];
              return [
                ` Diferenca: ${fmtBRL(ctx.parsed.x)}`,
                ` NF: ${fmtBRL(d.valor_nf)}`,
                ` MP: ${fmtBRL(d.valor_pago_mp)}`,
              ];
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true, grid: { color: '#f1f5f9' },
          ticks: {
            font: CHART_FONT, color: CHART_COLOR,
            callback(v) { return v >= 1000 ? 'R$' + (v / 1000).toFixed(1) + 'k' : 'R$' + v; },
          },
        },
        y: { grid: { display: false }, ticks: { font: CHART_FONT, color: CHART_COLOR } },
      },
    },
  });
}

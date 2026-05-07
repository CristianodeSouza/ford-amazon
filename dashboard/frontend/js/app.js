// ── CONFIG ────────────────────────────────────────────────────────────────────
const SHEETS_ID    = '1gaZhv11XyIAPFi87GLPaVI-KKg8gb22N-XTNNxZ83cQ';
const MAKE_WEBHOOK = '';   // URL webhook Make p/ disparar cenário (opcional)

// ── Detecção de ambiente ───────────────────────────────────────────────────────
const IS_LOCAL = ['localhost', '127.0.0.1'].includes(window.location.hostname);

// ── Cache de linhas brutas (modo Sheets) ──────────────────────────────────────
let _rawRows     = null;
let _rawAt       = null;
let _pendingFetch = null;
const CACHE_TTL  = 60_000;

// ── Chart.js instances (fora do Alpine para evitar reatividade) ───────────────
let _chartStatus = null;
let _chartMensal = null;
let _chartTopDiv = null;

// ══════════════════════════════════════════════════════════════════════════════
// Helpers de dados (modo Sheets)
// ══════════════════════════════════════════════════════════════════════════════

function _parseCurrency(v) {
  if (v == null || String(v).trim() === '') return null;
  try {
    const s = String(v).replace(/R\$/, '').replace(/\s/g, '').replace(/\./g, '').replace(',', '.');
    const n = parseFloat(s);
    return isNaN(n) ? null : n;
  } catch { return null; }
}

function _parseDate(s) {
  s = String(s || '').trim();
  const m1 = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m1) { try { return new Date(+m1[3], +m1[2] - 1, +m1[1]); } catch { return null; } }
  const m2 = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m2) { try { return new Date(+m2[1], +m2[2] - 1, +m2[3]); } catch { return null; } }
  return null;
}

function _mesChave(s) {
  s = String(s || '');
  const m1 = s.match(/(\d{1,2})\/(\d{4})/);
  const m2 = s.match(/(\d{4})-(\d{2})/);
  let mes, ano;
  if (m1)      { mes = parseInt(m1[1]); ano = m1[2]; }
  else if (m2) { mes = parseInt(m2[2]); ano = m2[1]; }
  else return null;
  const nomes = ['','Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
  try { return `${nomes[mes]}/${ano.slice(2)}`; } catch { return null; }
}

function _buildRegistros(rows) {
  if (!rows || rows.length < 2) return [];
  const result = [];
  for (const row of rows.slice(1)) {
    if (!row || !row.some(c => c)) continue;
    const nf = (row[0] || '').trim();
    if (!nf) continue;
    const valorNf   = _parseCurrency(row[3]);
    const valorPago = _parseCurrency(row[4]);
    const diferenca = valorNf != null && valorPago != null
      ? Math.round((valorNf - valorPago) * 100) / 100 : null;
    result.push({
      nota_fiscal:   nf,
      data_venda:    (row[1] || '').trim(),
      cliente:       (row[2] || '').trim(),
      valor_nf:      valorNf,
      valor_pago_mp: valorPago,
      custo_medio:   _parseCurrency(row[5]),
      desconto:      _parseCurrency(row[6]),
      percentual:    (row[7] || '').trim(),
      id_operacao:   (row[9] || '').trim(),
      diferenca,
      tipo: valorPago != null && valorPago < 0 ? 'disputa' : 'normal',
    });
  }
  return result;
}

function _filtrarPorData(registros, dataInicio, dataFim) {
  if (!dataInicio && !dataFim) return registros;
  const dtIni = dataInicio ? new Date(dataInicio + 'T00:00:00') : null;
  const dtFim = dataFim    ? new Date(dataFim    + 'T23:59:59') : null;
  return registros.filter(r => {
    const dt = _parseDate(r.data_venda);
    if (!dt) return false;
    if (dtIni && dt < dtIni) return false;
    if (dtFim && dt > dtFim) return false;
    return true;
  });
}

function _calcStatus(r) {
  if (r.valor_nf == null || r.valor_pago_mp == null) return 'sem_dados';
  if (r.tipo === 'disputa') return 'disputa';
  if (r.diferenca != null && Math.abs(r.diferenca) <= 0.01) return 'ok';
  return 'divergente';
}

function _calcResumo(registros) {
  const normais  = registros.filter(r => r.tipo === 'normal');
  const disputas = registros.filter(r => r.tipo === 'disputa');
  const rnd = v => Math.round(v * 100) / 100;
  const soma = (l, k) => rnd(l.reduce((a, r) => a + (r[k] || 0), 0));
  return {
    total:          registros.length,
    total_normais:  normais.length,
    total_disputas: disputas.length,
    nf_normais:     soma(normais,   'valor_nf'),
    pago_normais:   soma(normais,   'valor_pago_mp'),
    diff_normais:   rnd(soma(normais, 'valor_nf') - soma(normais, 'valor_pago_mp')),
    nf_disputas:    soma(disputas,  'valor_nf'),
    pago_disputas:  soma(disputas,  'valor_pago_mp'),
    nf_total:       soma(registros, 'valor_nf'),
    pago_total:     soma(registros, 'valor_pago_mp'),
    diff_total:     rnd(soma(registros, 'valor_nf') - soma(registros, 'valor_pago_mp')),
  };
}

function _calcInd(registros) {
  const ws = registros.map(r => ({ ...r, _s: _calcStatus(r) }));
  const normais  = ws.filter(r => r.tipo === 'normal');
  const disputas = ws.filter(r => r.tipo === 'disputa');
  const total_ok  = normais.filter(r => r._s === 'ok').length;
  const total_div = normais.filter(r => r._s === 'divergente').length;
  const total_sem = ws.filter(r => r._s === 'sem_dados').length;
  const total_dis = disputas.length;
  const base = total_ok + total_div + total_sem;
  const taxa = base > 0 ? Math.round(total_ok / base * 1000) / 10 : 0;
  const rnd = v => Math.round(v * 100) / 100;
  const soma = (l, k) => rnd(l.reduce((a, r) => a + (r[k] || 0), 0));
  const val_fat = soma(normais, 'valor_nf');
  const val_rec = soma(normais, 'valor_pago_mp');
  const val_tax = rnd(val_fat - val_rec);
  const val_dis = rnd(disputas.reduce((a, r) => a + Math.abs(r.valor_pago_mp || 0), 0));
  const saldo   = rnd(val_rec - val_dis);

  const mensal = {};
  for (const r of normais) {
    const k = _mesChave(r.data_venda);
    if (!k) continue;
    if (!mensal[k]) mensal[k] = { f: 0, r: 0 };
    mensal[k].f += r.valor_nf || 0;
    mensal[k].r += r.valor_pago_mp || 0;
  }
  const _ord = {Jan:1,Fev:2,Mar:3,Abr:4,Mai:5,Jun:6,Jul:7,Ago:8,Set:9,Out:10,Nov:11,Dez:12};
  const _sk  = k => { const p = k.split('/'); return [p[1] ? +p[1] : 0, _ord[p[0]] || 0]; };
  const evolucao = Object.entries(mensal)
    .sort((a, b) => { const [ay,am] = _sk(a[0]), [by,bm] = _sk(b[0]); return ay - by || am - bm; })
    .map(([mes, v]) => ({ mes, faturado: rnd(v.f), recebido: rnd(v.r) }));

  const top_div = ws
    .filter(r => r._s === 'divergente')
    .sort((a, b) => Math.abs(b.diferenca || 0) - Math.abs(a.diferenca || 0))
    .slice(0, 10)
    .map(r => ({ nota_fiscal: r.nota_fiscal, cliente: r.cliente, diferenca: r.diferenca, valor_nf: r.valor_nf, valor_pago_mp: r.valor_pago_mp }));

  const pct = (n, d) => d ? Math.round(n / d * 1000) / 10 : 0;
  return {
    taxa_conciliacao: taxa,
    total_ok, total_divergente: total_div, total_disputa: total_dis, total_sem_dados: total_sem,
    valor_faturado: val_fat, valor_recebido: val_rec,
    valor_taxas: val_tax, valor_disputas: val_dis, saldo_liquido: saldo,
    pct_taxas:    pct(val_tax, val_fat),
    pct_disputas: pct(val_dis, val_fat),
    pct_recebido: pct(val_rec, val_fat),
    evolucao_mensal:  evolucao,
    top_divergencias: top_div,
  };
}

async function _fetchSheetsRows(forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && _rawRows && _rawAt && (now - _rawAt) < CACHE_TTL) return _rawRows;
  if (!_pendingFetch) {
    _pendingFetch = (async () => {
      // gviz/tq funciona para planilhas compartilhadas publicamente — sem API key
      const sheet = encodeURIComponent('Página2');
      const url   = `https://docs.google.com/spreadsheets/d/${SHEETS_ID}/gviz/tq?tqx=out:json&sheet=${sheet}`;
      const res   = await fetch(url);
      if (!res.ok) throw new Error(`Sheets: HTTP ${res.status}`);
      const text  = await res.text();
      // Remove o wrapper JSONP: "/*O_o*/\ngoogle.visualization.Query.setResponse({...});"
      const json  = JSON.parse(text.replace(/^[^(]+\(/, '').replace(/\);\s*$/, ''));
      if (json.status !== 'ok') throw new Error(json.errors?.[0]?.message || 'Planilha inacessível');
      // Converte formato gviz → rows[][]  (linha 0 = cabeçalho)
      const header = json.table.cols.map(c => c.label || c.id || '');
      const rows   = [
        header,
        ...json.table.rows.map(row =>
          (row.c || []).map(cell => {
            if (!cell || cell.v == null) return '';
            // Usa o valor formatado (f) quando disponível — preserva formato BR de moeda e data
            return cell.f != null ? String(cell.f) : String(cell.v);
          })
        ),
      ];
      _rawRows      = rows;
      _rawAt        = Date.now();
      _pendingFetch = null;
      return _rawRows;
    })();
  }
  return _pendingFetch;
}

// ══════════════════════════════════════════════════════════════════════════════
// Alpine.js — componente principal
// ══════════════════════════════════════════════════════════════════════════════
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
    buscaId: '',
    dataInicio: '',
    dataFim: '',
    loading: true,
    loadingInd: true,
    aviso: null,
    ultimaAtualizacao: null,

    async init() {
      await Promise.all([this.carregar(), this.carregarIndicadores()]);
    },

    _buildParams() {
      const p = new URLSearchParams();
      if (!this.buscaNF.trim()) {
        if (this.dataInicio) p.append('data_inicio', this.dataInicio);
        if (this.dataFim)    p.append('data_fim',    this.dataFim);
      }
      if (this.buscaNF.trim())      p.append('nota_fiscal', this.buscaNF.trim());
      if (this.buscaCliente.trim()) p.append('cliente',     this.buscaCliente.trim());
      if (this.buscaId.trim())      p.append('id_operacao', this.buscaId.trim());
      return p;
    },

    // ── Carregar tabela ───────────────────────────────────────────────────────
    async carregar() {
      this.loading = true;
      this.aviso   = null;
      try {
        if (IS_LOCAL) {
          // Modo local: usa o backend FastAPI
          const params = this._buildParams();
          if (this.aba !== 'todos') params.append('tipo', this.aba);
          const res = await fetch('/api/conciliacao?' + params.toString());
          if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);
          const data = await res.json();
          this.registros = data.registros || [];
          this.resumo    = data.resumo    || this.resumo;
          this.total     = data.total     || 0;
          this.aviso     = data.aviso     || null;
        } else {
          // Modo Sheets: busca tudo e filtra localmente
          const rows = await _fetchSheetsRows();
          let all = _buildRegistros(rows);

          // Filtro de data (ignorado quando busca por NF específica)
          const nfBusca = this.buscaNF.trim();
          if (!nfBusca && (this.dataInicio || this.dataFim)) {
            all = _filtrarPorData(all, this.dataInicio, this.dataFim);
          }

          // Filtros textuais
          if (nfBusca) {
            const t = nfBusca.toLowerCase();
            all = all.filter(r => String(r.nota_fiscal).toLowerCase().includes(t));
          }
          if (this.buscaCliente.trim()) {
            const t = this.buscaCliente.trim().toLowerCase();
            all = all.filter(r => r.cliente.toLowerCase().includes(t));
          }
          if (this.buscaId.trim()) {
            const t = this.buscaId.trim().toLowerCase();
            all = all.filter(r => String(r.id_operacao || '').toLowerCase().includes(t));
          }

          // Resumo reflete os filtros ativos
          this.resumo = _calcResumo(all);

          const shown = this.aba !== 'todos' ? all.filter(r => r.tipo === this.aba) : all;
          this.registros = shown;
          this.total     = shown.length;
        }

        const agora = new Date();
        this.ultimaAtualizacao = agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        this.aviso = 'Não foi possível carregar os dados: ' + e.message;
      } finally {
        this.loading = false;
      }
    },

    // ── Carregar indicadores ──────────────────────────────────────────────────
    async carregarIndicadores() {
      this.loadingInd = true;
      try {
        if (IS_LOCAL) {
          const params = this._buildParams();
          const res = await fetch('/api/indicadores?' + params.toString());
          if (!res.ok) throw new Error(`Erro HTTP ${res.status}`);
          const data = await res.json();
          if (data.erro) return;
          Object.assign(this.ind, data);
        } else {
          const rows = await _fetchSheetsRows();
          let all = _buildRegistros(rows);
          const nfBusca = this.buscaNF.trim();
          if (!nfBusca && (this.dataInicio || this.dataFim)) {
            all = _filtrarPorData(all, this.dataInicio, this.dataFim);
          }
          if (nfBusca) {
            const t = nfBusca.toLowerCase();
            all = all.filter(r => String(r.nota_fiscal).toLowerCase().includes(t));
          }
          if (this.buscaCliente.trim()) {
            const t = this.buscaCliente.trim().toLowerCase();
            all = all.filter(r => r.cliente.toLowerCase().includes(t));
          }
          if (this.buscaId.trim()) {
            const t = this.buscaId.trim().toLowerCase();
            all = all.filter(r => String(r.id_operacao || '').toLowerCase().includes(t));
          }
          Object.assign(this.ind, _calcInd(all));
        }
        await this.$nextTick();
        inicializarGraficos(this.ind);
      } catch (e) {
        console.warn('Indicadores:', e.message);
      } finally {
        this.loadingInd = false;
      }
    },

    async aplicarFiltros() {
      await Promise.all([this.carregar(), this.carregarIndicadores()]);
    },

    limparFiltros() {
      this.buscaNF      = '';
      this.buscaCliente = '';
      this.buscaId      = '';
      this.dataInicio   = '';
      this.dataFim      = '';
      this.aplicarFiltros();
    },

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

    labelPeriodo() {
      const fmt = d => d ? new Date(d + 'T12:00:00').toLocaleDateString('pt-BR') : null;
      const ini = fmt(this.dataInicio);
      const fim = fmt(this.dataFim);
      if (ini && fim) return `${ini} a ${fim}`;
      if (ini)        return `A partir de ${ini}`;
      if (fim)        return `Até ${fim}`;
      return '';
    },

    // ── Atualizar dados ───────────────────────────────────────────────────────
    async atualizar() {
      this.loading    = true;
      this.loadingInd = true;
      this.aviso      = null;
      try {
        if (IS_LOCAL) {
          await fetch('/api/refresh', { method: 'POST' });
        } else {
          // Limpa cache para forçar re-leitura da planilha
          _rawRows      = null;
          _rawAt        = null;
          _pendingFetch = null;
          // Se webhook Make configurado, dispara o cenário para buscar dados frescos
          if (MAKE_WEBHOOK) {
            fetch(MAKE_WEBHOOK, { method: 'POST' }).catch(() => {});
            await new Promise(r => setTimeout(r, 5000));
          }
        }
        await this.aplicarFiltros();
      } catch (e) {
        this.aviso      = 'Erro ao atualizar: ' + e.message;
        this.loading    = false;
        this.loadingInd = false;
      }
    },

    // ── Formatadores ──────────────────────────────────────────────────────────
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

    // ── Status de cada registro ───────────────────────────────────────────────
    statusReg(r)       { return _calcStatus(r); },
    statusLabel(r)     { return { ok: 'Conciliada', divergente: 'Divergente', disputa: 'Disputa', sem_dados: 'Sem Dados' }[this.statusReg(r)] || '—'; },
    statusBadgeClass(r){ return { ok: 'sbadge-ok', divergente: 'sbadge-div', disputa: 'sbadge-disp', sem_dados: 'sbadge-sem' }[this.statusReg(r)] || ''; },

    // ── Ação recomendada ──────────────────────────────────────────────────────
    acaoTag(r) {
      const s = this.statusReg(r);
      if (s === 'ok')         return 'Arquivar';
      if (s === 'disputa')    return 'Contestar';
      if (s === 'sem_dados')  return 'Investigar';
      if (s === 'divergente') return r.diferenca > 0 ? 'Checar taxa' : 'Checar NF';
      return '—';
    },
    acaoTagClass(r) { return { ok: 'atag-ok', divergente: 'atag-div', disputa: 'atag-disp', sem_dados: 'atag-sem' }[this.statusReg(r)] || ''; },

    // ── Classes da tabela ─────────────────────────────────────────────────────
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

    // ── Exportar planilha CSV ─────────────────────────────────────────────────
    exportarPlanilha() {
      if (!this.registros.length) return;

      const BOM = '﻿';   // BOM para Excel abrir UTF-8 corretamente
      const SEP = ';';
      const rnd2 = v => v != null ? Number(v).toFixed(2).replace('.', ',') : '';
      const esc  = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const hoje = new Date().toLocaleDateString('pt-BR');

      const linhas = [];

      // ── Cabeçalho ──
      linhas.push([esc('CONCILIAÇÃO FORD AMAZON'), esc(hoje)].join(SEP));
      if (this.labelPeriodo()) linhas.push([esc('Período'), esc(this.labelPeriodo())].join(SEP));
      linhas.push([esc('Aba'), esc(this.abaLabel())].join(SEP));
      linhas.push('');

      // ── Resumo ──
      linhas.push(esc('RESUMO DE CONCILIAÇÃO'));
      linhas.push([esc('Total de Registros'),          esc(this.resumo.total)].join(SEP));
      linhas.push([esc('Transações Normais'),           esc(this.resumo.total_normais)].join(SEP));
      linhas.push([esc('Disputas / Chargebacks'),       esc(this.resumo.total_disputas)].join(SEP));
      linhas.push([esc('Valor Faturado NF (R$)'),       esc(rnd2(this.resumo.nf_total))].join(SEP));
      linhas.push([esc('Valor Recebido MP (R$)'),       esc(rnd2(this.resumo.pago_total))].join(SEP));
      linhas.push([esc('Diferença Total (R$)'),         esc(rnd2(this.resumo.diff_total))].join(SEP));
      linhas.push([esc('Taxa de Conciliação (%)'),      esc(this.ind.taxa_conciliacao)].join(SEP));
      linhas.push([esc('Conciliadas OK'),               esc(this.ind.total_ok)].join(SEP));
      linhas.push([esc('Divergentes'),                  esc(this.ind.total_divergente)].join(SEP));
      linhas.push([esc('Disputas'),                     esc(this.ind.total_disputa)].join(SEP));
      linhas.push([esc('Saldo Líquido Final (R$)'),     esc(rnd2(this.ind.saldo_liquido))].join(SEP));
      linhas.push('');

      // ── Detalhamento ──
      linhas.push(esc('DETALHAMENTO DOS REGISTROS'));
      const cols = [
        'Nota Fiscal', 'Data Venda', 'Cliente',
        'Valor NF (R$)', 'Valor Pago MP (R$)', 'Diferença (R$)',
        'Status', 'Ação Recomendada', 'ID Operação',
      ];
      linhas.push(cols.map(esc).join(SEP));

      for (const r of this.registros) {
        linhas.push([
          esc(r.nota_fiscal),
          esc(r.data_venda),
          esc(r.cliente),
          esc(rnd2(r.valor_nf)),
          esc(rnd2(r.valor_pago_mp)),
          esc(rnd2(r.diferenca)),
          esc(this.statusLabel(r)),
          esc(this.acaoTag(r)),
          esc(r.id_operacao),
        ].join(SEP));
      }

      const csv  = BOM + linhas.join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `Conciliacao_Ford_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },

    abaLabel() {
      if (this.aba === 'normal')  return 'Transações Normais';
      if (this.aba === 'disputa') return 'Disputas / Chargebacks';
      return 'Todos os registros';
    },
  };
}

// ══════════════════════════════════════════════════════════════════════════════
// Chart.js — funções externas (sem reatividade Alpine)
// ══════════════════════════════════════════════════════════════════════════════

const CORES = {
  ok: '#16a34a', div: '#d97706', disp: '#dc2626', sem: '#94a3b8',
  ford: '#003087', fordMid: '#0050d0', green: '#16a34a',
};
const CHART_FONT  = { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", size: 11 };
const CHART_COLOR = '#64748b';

function fmtBRL(v) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2 }).format(v);
}

function inicializarGraficos(ind) {
  buildChartStatus(ind);
  buildChartMensal(ind);
  buildChartTopDiv(ind);
}

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
        tooltip: { callbacks: { label(ctx) {
          const v = ctx.parsed;
          const pct = total > 0 ? ((v / total) * 100).toFixed(1) : 0;
          return ` ${v} NF(s) — ${pct}%`;
        }}},
      },
    },
  });
}

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
        { label: 'Faturado (NF)', data: dados.map(d => d.faturado),
          backgroundColor: 'rgba(0,48,135,0.80)', borderColor: CORES.ford, borderWidth: 1, borderRadius: 4 },
        { label: 'Recebido (MP)', data: dados.map(d => d.recebido),
          backgroundColor: 'rgba(22,163,74,0.75)', borderColor: CORES.green, borderWidth: 1, borderRadius: 4 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label(ctx) { return ` ${ctx.dataset.label}: ${fmtBRL(ctx.parsed.y)}`; } } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: CHART_FONT, color: CHART_COLOR } },
        y: { beginAtZero: true, grid: { color: '#f1f5f9' },
          ticks: { font: CHART_FONT, color: CHART_COLOR,
            callback(v) { return v >= 1000 ? 'R$' + (v / 1000).toFixed(0) + 'k' : 'R$' + v; } } },
      },
    },
  });
}

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
        tooltip: { callbacks: {
          title(items) { return `NF: ${dados[items[0].dataIndex].nota_fiscal}`; },
          label(ctx) {
            const d = dados[ctx.dataIndex];
            return [
              ` Diferença: ${fmtBRL(ctx.parsed.x)}`,
              ` NF: ${fmtBRL(d.valor_nf)}`,
              ` MP: ${fmtBRL(d.valor_pago_mp)}`,
            ];
          },
        }},
      },
      scales: {
        x: { beginAtZero: true, grid: { color: '#f1f5f9' },
          ticks: { font: CHART_FONT, color: CHART_COLOR,
            callback(v) { return v >= 1000 ? 'R$' + (v / 1000).toFixed(1) + 'k' : 'R$' + v; } } },
        y: { grid: { display: false }, ticks: { font: CHART_FONT, color: CHART_COLOR } },
      },
    },
  });
}

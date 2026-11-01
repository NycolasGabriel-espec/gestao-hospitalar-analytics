const API = {
  executive: '/api/executive?limit=1000',
  risk: '/api/risk',
  benchmark: '/api/benchmark',
};
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const $ = (id) => document.getElementById(id);
const state = { executive: [], risks: [], months: [], lastUpdated: null, riskRequest: 0, riskLoading: false, riskError: '', benchmark: null, benchmarkLoading: false, benchmarkError: '' };
const SVG = 'http://www.w3.org/2000/svg';
const BENCHMARK_COLORS = ['#177b73', '#4f7891', '#c18440', '#6d7da7', '#8b6d91', '#7b8d58'];
const SIGTAP_DESCRIPTIONS = {
  '0303010037': 'Tratamento de outras doenças bacterianas',
  '0303040149': 'Tratamento de AVC agudo',
  '0303140151': 'Tratamento de pneumonias ou influenza',
  '0303160063': 'Transtornos respiratórios e cardiovasculares neonatais',
  '0310010039': 'Parto normal',
  '0406010587': 'Implante de cardioversor-desfibrilador de câmara dupla',
  '0406010609': 'Implante de cardioversor-desfibrilador multi-sítio',
  '0406010935': 'Revascularização miocárdica com circulação extracorpórea',
  '0411010034': 'Parto cesariano',
  '0415010012': 'Tratamento com cirurgias múltiplas',
  '0415020050': 'Procedimentos sequenciais em oncologia',
};

function element(name, className, text) {
  const node = document.createElement(name);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function getJson(path) {
  const response = await fetch(path, {
    method: 'GET',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  });
  if (response.status === 401 || response.status === 403) {
    const error = new Error('access');
    error.access = true;
    error.status = response.status;
    throw error;
  }
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) {
    const error = new Error(payload.error || 'Não foi possível carregar os dados.');
    error.status = response.status;
    throw error;
  }
  return payload.data || [];
}

function setStatus(message, kind = 'ready') {
  const strip = $('data-status');
  strip.dataset.state = kind;
  $('status-text').textContent = message;
  $('last-updated').textContent = state.lastUpdated
    ? `Atualizado às ${new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(state.lastUpdated)}`
    : '';
}

function showAccess(message) {
  $('access-message').textContent = message;
  $('access-overlay').hidden = false;
  $('status-text').textContent = message;
  $('data-status').dataset.state = 'error';
}

function valueOrDash(value, formatter = number) {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return '—';
  return formatter.format(Number(value));
}

function isKnownNumber(value) {
  return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
}

function selectedRows() {
  const period = $('period-filter').value;
  const specialty = $('specialty-filter').value;
  return state.executive.filter((row) =>
    (period === 'all' || row.ano_mes === period)
    && (specialty === 'all' || row.especialidade === specialty));
}

function appendOption(select, value, label) {
  const option = document.createElement('option');
  option.value = value;
  option.textContent = label;
  select.append(option);
}

function monthLabel(value) {
  if (!/^\d{4}-\d{2}$/.test(value || '')) return value || '—';
  const [year, month] = value.split('-');
  return `${month}/${year.slice(2)}`;
}

function fullMonthLabel(value) {
  if (!/^\d{4}-\d{2}$/.test(value || '')) return 'período indisponível';
  const [year, month] = value.split('-');
  return new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(Date.UTC(Number(year), Number(month) - 1, 1, 12)));
}

function availablePeriodLabel() {
  const periods = state.months.map((item) => item.ano_mes).sort((a, b) => a.localeCompare(b));
  if (!periods.length) return 'sem competências de admissão em 2025';
  return 'janeiro a dezembro de 2025';
}

function selectedPeriodLabel() {
  const period = $('period-filter').value;
  return period === 'all' ? availablePeriodLabel() : fullMonthLabel(period);
}

function trendPeriodLabel() {
  const period = $('period-filter').value;
  if (period !== 'all') return fullMonthLabel(period);
  const specialty = $('specialty-filter').value;
  const months = [...new Set(state.executive
    .filter((row) => specialty === 'all' || row.especialidade === specialty)
    .map((row) => row.ano_mes)
    .filter(Boolean))]
    .sort((a, b) => a.localeCompare(b))
    .slice(-12);
  if (!months.length) return 'período indisponível';
  if (months.length === 1) return fullMonthLabel(months[0]);
  return `${fullMonthLabel(months[0])} a ${fullMonthLabel(months.at(-1))}`;
}

function updatePeriodCopy() {
  const available = availablePeriodLabel();
  const period = $('period-filter').value;
  $('period-summary').textContent = `Alagoas · competências ${available}`;
  $('source-period').textContent = `Competências: ${available}`;
  $('trend-copy').textContent = period === 'all'
    ? `${state.months.length > 12 ? 'Até 12 competências mais recentes' : 'Série completa'} · ${trendPeriodLabel()} · contagem agregada nas coortes liberadas`
    : `Competência ${trendPeriodLabel()} · contagem agregada nas coortes liberadas`;
}

function configureFilters() {
  const period = $('period-filter');
  const specialty = $('specialty-filter');
  period.replaceChildren();
  appendOption(period, 'all', 'Ano completo · jan–dez/2025');
  state.months.forEach((item) => appendOption(period, item.ano_mes, monthLabel(item.ano_mes)));
  period.value = 'all';

  specialty.replaceChildren();
  appendOption(specialty, 'all', 'Todas as especialidades');
  [...new Set(state.executive.map((item) => item.especialidade).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, 'pt-BR'))
    .forEach((item) => appendOption(specialty, item, item));
  period.disabled = false;
  specialty.disabled = false;
}

function renderMetrics(rows) {
  const volume = rows.reduce((sum, row) => sum + (Number(row.volume_internacoes) || 0), 0);
  $('metric-admissions').textContent = rows.length ? number.format(volume) : '—';
  $('specialty-count').textContent = rows.length ? `${rows.length} ${rows.length === 1 ? 'grupo' : 'grupos'}` : 'sem grupos';

  const completeStay = rows.length > 0 && rows.every((row) => isKnownNumber(row.tmp_medio) && Number(row.volume_internacoes) > 0);
  const weightedStay = completeStay
    ? rows.reduce((sum, row) => sum + Number(row.tmp_medio) * Number(row.volume_internacoes), 0) / volume
    : null;
  $('metric-stay').textContent = weightedStay === null ? '—' : `${decimal.format(weightedStay)} d`;

  const completeAmounts = rows.length > 0 && rows.every((row) => isKnownNumber(row.receita_total));
  const amount = completeAmounts ? rows.reduce((sum, row) => sum + Number(row.receita_total), 0) : null;
  $('metric-aihs').textContent = amount === null ? '—' : currency.format(amount);
}

function svgNode(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG, tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderTrend() {
  const period = $('period-filter').value;
  const specialty = $('specialty-filter').value;
  const byMonth = new Map();
  state.executive
    .filter((row) => (period === 'all' || row.ano_mes === period)
      && (specialty === 'all' || row.especialidade === specialty))
    .forEach((row) => byMonth.set(row.ano_mes, (byMonth.get(row.ano_mes) || 0) + (Number(row.volume_internacoes) || 0)));
  const points = [...byMonth.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-12);
  const host = $('trend-chart');
  host.replaceChildren();
  if (!points.length) {
    host.append(element('div', 'chart-empty', 'Ainda não há meses de admissão disponíveis para esta seleção.'));
    return;
  }

  const width = 760, height = 230, left = 48, right = 12, top = 14, bottom = 34;
  const plotW = width - left - right, plotH = height - top - bottom;
  const max = Math.max(1, ...points.map(([, v]) => v));
  const stepX = points.length > 1 ? plotW / (points.length - 1) : 0;
  const coords = points.map(([month, value], index) => ({
    month, value,
    x: points.length > 1 ? left + index * stepX : left + plotW / 2,
    y: top + plotH - (value / max) * plotH,
  }));
  const chart = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, class: 'trend-svg', role: 'img', 'aria-label': `Internações agregadas por mês de admissão em ${trendPeriodLabel()}` });
  const title = svgNode('title', {}, `Internações por mês de admissão, ${trendPeriodLabel()}`);
  chart.append(title);
  for (let line = 0; line <= 3; line += 1) {
    const y = top + (plotH / 3) * line;
    const label = Math.round(max * (1 - line / 3));
    chart.append(svgNode('line', { x1: left, y1: y, x2: width - right, y2: y, class: 'grid-line' }));
    chart.append(svgNode('text', { x: left - 9, y: y + 3.5, 'text-anchor': 'end', class: 'axis-label' }, number.format(label)));
  }
  const linePath = coords.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
  const areaPath = `${linePath} L ${coords.at(-1).x} ${top + plotH} L ${coords[0].x} ${top + plotH} Z`;
  chart.append(svgNode('path', { d: areaPath, class: 'trend-area' }));
  chart.append(svgNode('path', { d: linePath, class: 'trend-line' }));
  coords.forEach((point, index) => {
    const circle = svgNode('circle', { cx: point.x, cy: point.y, r: index === coords.length - 1 ? 5 : 3.5, class: `trend-point${index === coords.length - 1 ? ' latest' : ''}` });
    circle.append(svgNode('title', {}, `${point.month}: ${number.format(point.value)} internações em grupos publicados`));
    chart.append(circle);
    chart.append(svgNode('text', { x: point.x, y: height - 9, 'text-anchor': 'middle', class: 'axis-label' }, monthLabel(point.month)));
  });
  host.append(chart);
}

function renderRanking(rows) {
  const host = $('specialty-ranking');
  host.replaceChildren();
  if (!rows.length) {
    host.append(element('div', 'chart-empty', 'Sem grupos publicados nesta seleção.'));
    return;
  }
  const bySpecialty = new Map();
  rows.forEach((row) => {
    const name = row.especialidade || 'Não classificada';
    bySpecialty.set(name, (bySpecialty.get(name) || 0) + Number(row.volume_internacoes || 0));
  });
  const sorted = [...bySpecialty].map(([especialidade, volume_internacoes]) => ({ especialidade, volume_internacoes }))
    .sort((a, b) => b.volume_internacoes - a.volume_internacoes).slice(0, 6);
  const maximum = Math.max(1, ...sorted.map((row) => Number(row.volume_internacoes) || 0));
  sorted.forEach((row) => {
    const line = element('div', 'rank-row');
    const name = element('span', 'rank-name', row.especialidade || 'Não classificada');
    name.title = row.especialidade || 'Não classificada';
    const track = element('span', 'rank-track');
    const fill = element('span', 'rank-fill');
    fill.style.width = `${Math.max(2, (Number(row.volume_internacoes || 0) / maximum) * 100)}%`;
    track.append(fill);
    line.append(name, track, element('span', 'rank-value', valueOrDash(row.volume_internacoes)));
    host.append(line);
  });
  host.append(element('div', 'rank-foot', 'Escala relativa aos grupos exibidos nesta seleção.'));
}

function renderOutcomes(rows) {
  const host = $('outcomes-list');
  host.replaceChildren();
  const allPeriods = $('period-filter').value === 'all';
  $('outcomes-title').textContent = allPeriods ? 'Mortalidade por especialidade e mês' : 'Mortalidade por especialidade';
  const available = rows.filter((row) => isKnownNumber(row.taxa_mortalidade_pct))
    .sort((a, b) => Number(b.taxa_mortalidade_pct) - Number(a.taxa_mortalidade_pct)).slice(0, 5);
  if (!available.length) {
    host.append(element('p', 'outcome-empty', 'Indicador de óbito não disponível nesta seleção. A fonte pode ter desfechos ausentes.'));
    return;
  }
  const maximum = Math.max(1, ...available.map((row) => Number(row.taxa_mortalidade_pct)));
  available.forEach((row) => {
    const line = element('div', 'outcome-row');
    const name = `${row.especialidade || 'Não classificada'}${allPeriods ? ` · ${monthLabel(row.ano_mes)}` : ''}`;
    line.append(element('span', 'outcome-name', name));
    const track = element('span', 'outcome-track');
    const fill = element('span', 'outcome-fill');
    fill.style.width = `${Math.max(2, Number(row.taxa_mortalidade_pct) / maximum * 100)}%`;
    track.append(fill);
    line.append(track, element('span', 'outcome-value', `${decimal.format(Number(row.taxa_mortalidade_pct))}%`));
    host.append(line);
  });
}

function renderDiagnoses() {
  const period = $('period-filter').value;
  const specialty = $('specialty-filter').value;
  const rows = state.risks.filter((row) =>
    (period === 'all' || row.ano_mes === period)
    && (specialty === 'all' || row.especialidade === specialty))
    .sort((a, b) => Number(b.volume_internacoes || 0) - Number(a.volume_internacoes || 0))
    .slice(0, 10);
  const body = $('diagnosis-rows');
  body.replaceChildren();
  if (state.riskLoading || state.riskError) {
    const row = document.createElement('tr');
    const cell = element('td', 'table-empty', state.riskLoading ? 'Consultando as coortes da seleção…' : state.riskError);
    cell.colSpan = 7;
    row.append(cell);
    body.append(row);
    $('diagnosis-footnote').textContent = '';
    return;
  }
  if (!rows.length) {
    const row = document.createElement('tr');
    const cell = element('td', 'table-empty', 'Sem coortes CID-10 publicadas para esta seleção.');
    cell.colSpan = 7;
    row.append(cell);
    body.append(row);
    $('diagnosis-footnote').textContent = '';
    return;
  }
  rows.forEach((item) => {
    const row = document.createElement('tr');
    const code = element('td', 'code', item.cid_10 || '—');
    const diagnosis = element('td', '', item.descricao_cid || 'Descrição não informada');
    const specialtyCell = element('td', '', item.especialidade || 'Não classificada');
    const age = element('td', '', item.faixa_etaria || 'Não informada');
    const volume = element('td', 'num', valueOrDash(item.volume_internacoes));
    const stay = element('td', 'num', item.tmp_medio === null ? '—' : `${valueOrDash(item.tmp_medio, decimal)} d`);
    const mortality = element('td', 'num', item.taxa_mortalidade_pct === null ? '—' : `${valueOrDash(item.taxa_mortalidade_pct, decimal)}%`);
    row.append(code, diagnosis, specialtyCell, age, volume, stay, mortality);
    body.append(row);
  });
  $('diagnosis-footnote').textContent = 'Até 10 coortes com maior volume na seleção. Supressão mínima de 10 internações por grupo; isso reduz exposição, mas não garante anonimização.';
}

async function loadRisks() {
  const request = ++state.riskRequest;
  state.riskLoading = true;
  state.riskError = '';
  state.risks = [];
  renderDiagnoses();
  const params = new URLSearchParams({ limit: '10' });
  if ($('period-filter').value !== 'all') params.set('ano_mes', $('period-filter').value);
  if ($('specialty-filter').value !== 'all') params.set('especialidade', $('specialty-filter').value);
  try {
    const risks = await getJson(`${API.risk}?${params}`);
    if (request === state.riskRequest) state.risks = risks;
  } catch (error) {
    if (request !== state.riskRequest) return;
    if (error.access) showAccess('Entre novamente com sua conta autorizada para consultar os dados.');
    else state.riskError = error.message || 'Não foi possível consultar as coortes.';
  } finally {
    if (request === state.riskRequest) {
      state.riskLoading = false;
      renderDiagnoses();
    }
  }
}

function render() {
  const rows = selectedRows();
  updatePeriodCopy();
  renderMetrics(rows);
  renderTrend();
  renderRanking(rows);
  renderOutcomes(rows);
  renderDiagnoses();
  if (!state.executive.length) setStatus('Sem dados publicados. Execute a extração PySUS, a transformação local e a carga autorizada para o MySQL.', 'error');
  else setStatus(`${number.format(rows.length)} grupos publicados na seleção. SIH/SUS · Alagoas · ${selectedPeriodLabel()} · agrupamento por admissão.`);
}

async function loadDashboard() {
  const refresh = $('refresh-button');
  refresh.classList.add('is-loading');
  setStatus('Consultando os dados autorizados…', 'loading');
  try {
    const executive = await getJson(API.executive);
    state.executive = executive;
    state.risks = [];
    state.months = [...new Set(executive.map((item) => item.ano_mes).filter(Boolean))]
      .sort((a, b) => b.localeCompare(a)).map((ano_mes) => ({ ano_mes }));
    state.lastUpdated = new Date();
    configureFilters();
    render();
    await loadRisks();
    $('last-updated').textContent = `Atualizado às ${new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(state.lastUpdated)}`;
  } catch (error) {
    if (error.access) {
      showAccess(error.status === 403
        ? 'Esta conta não está habilitada para acessar os dados. Solicite liberação à equipe responsável.'
        : 'O painel apresenta indicadores agregados do SIH/SUS. Acesse com a conta habilitada pela equipe responsável.');
    } else {
      setStatus(error.message || 'Não foi possível carregar os dados autorizados.', 'error');
      $('metric-admissions').textContent = '—';
      $('metric-stay').textContent = '—';
      $('metric-aihs').textContent = '—';
    }
  } finally {
    refresh.classList.remove('is-loading');
  }
}

function changeSelection() {
  render();
  loadRisks();
}
$('period-filter').addEventListener('change', changeSelection);
$('specialty-filter').addEventListener('change', changeSelection);
$('refresh-button').addEventListener('click', refreshDashboard);
$('benchmark-period').addEventListener('change', () => loadBenchmark());
$('logout-button').addEventListener('click', async () => {
  $('logout-button').disabled = true;
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } });
  } finally {
    window.location.assign('../login.html');
  }
});

function benchmarkRows() {
  if (!state.benchmark) return [];
  const period = $('benchmark-period').value;
  return state.benchmark.summary.filter((row) =>
    period === 'all' || row.ano_mes === period);
}

function configureBenchmarkFilters() {
  const { summary } = state.benchmark;
  const period = $('benchmark-period');
  period.replaceChildren();
  appendOption(period, 'all', 'Ano completo · jan–dez/2025');
  [...new Set(summary.map((row) => row.ano_mes).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b))
    .forEach((month) => appendOption(period, month, monthLabel(month)));
  period.value = 'all';
  period.disabled = false;
}

function setBenchmarkNotice(message, kind = 'ready') {
  $('benchmark-notice').dataset.state = kind;
  $('benchmark-status-text').textContent = message;
}

function benchmarkLabelForPeriod() {
  const period = $('benchmark-period').value;
  if (period !== 'all') return fullMonthLabel(period);
  return 'jan–dez/2025';
}

function renderBenchmarkMetadata() {
  const manifest = Array.isArray(state.benchmark?.meta?.datasetManifest)
    ? state.benchmark.meta.datasetManifest
    : [];
  const bySource = new Map(manifest.map((item) => [item.source_key, item]));
  const dateLabel = (value) => {
    if (!value) return 'sem data';
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? 'sem data'
      : new Intl.DateTimeFormat('pt-BR', {
        day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC',
      }).format(parsed);
  };
  const loadDateLabel = (value) => {
    const parsed = value ? new Date(value) : null;
    return parsed && !Number.isNaN(parsed.getTime())
      ? new Intl.DateTimeFormat('pt-BR', {
      dateStyle: 'short', timeStyle: 'short', timeZone: 'UTC',
      }).format(parsed)
      : 'sem data';
  };
  const segments = [
    ['sih_sus', 'SIH'], ['cnes', 'CNES'], ['sisreg', 'SISREG'],
  ].flatMap(([key, label]) => {
    const item = bySource.get(key);
    if (!item) return [];
    return [`${label} até ${dateLabel(item.data_through || item.coverage_end)} · carga ${loadDateLabel(item.loaded_at_utc)} UTC`];
  });
  $('benchmark-meta').textContent = segments.length
    ? segments.join(' · ')
    : 'Manifesto da carga indisponível · SISREG extraído em 10/08/2025';
  $('benchmark-meta').title = manifest.map((item) =>
    `${item.source_label}: cobertura ${dateLabel(item.coverage_start)} a ${dateLabel(item.coverage_end)}; `
    + `${number.format(Number(item.source_record_count) || 0)} registros de origem; `
    + `${number.format(Number(item.aggregate_row_count) || 0)} linhas agregadas.`
  ).join(' | ');
}

function renderBenchmarkMetrics(rows) {
  const volume = rows.reduce((sum, row) => sum + (Number(row.volume_aih) || 0), 0);
  const stay = volume && rows.every((row) => isKnownNumber(row.dias_permanencia))
    ? rows.reduce((sum, row) => sum + Number(row.dias_permanencia), 0) / volume
    : null;
  const completeAmount = rows.length > 0 && rows.every((row) => isKnownNumber(row.valor_aih_total));
  const amount = completeAmount ? rows.reduce((sum, row) => sum + Number(row.valor_aih_total), 0) : null;
  $('benchmark-volume').textContent = rows.length ? number.format(volume) : '—';
  $('benchmark-wait').textContent = stay === null ? '—' : `${decimal.format(stay)} d`;
  $('benchmark-cost').textContent = amount === null ? '—' : currency.format(amount);

  const period = $('benchmark-period').value;
  const occupancy = state.benchmark.occupancy.filter((row) => period === 'all' || row.ano_mes === period);
  const patientDays = occupancy.reduce((sum, row) => sum + Number(row.dias_paciente_sih || 0), 0);
  const bedDays = occupancy.reduce((sum, row) => sum + Number(row.leitos_dia_disponiveis || 0), 0);
  const rate = bedDays ? patientDays * 100 / bedDays : null;
  const averageBeds = occupancy.length
    ? occupancy.reduce((sum, row) => sum + Number(row.leitos_sus_cnes || 0), 0) / occupancy.length
    : null;
  $('benchmark-occupancy').textContent = rate === null ? '—' : `${decimal.format(rate)}%`;
  $('benchmark-occupancy-note').textContent = averageBeds === null
    ? 'Proxy SIH/CNES; sem capacidade publicada'
    : `${number.format(Math.round(averageBeds))} leitos SUS médios · proxy SIH/CNES`;
}

function renderBenchmarkWait() {
  const host = $('benchmark-wait-chart');
  host.replaceChildren();
  const sorted = [...(state.benchmark?.waiting || [])]
    .sort((a, b) => Number(b.espera_p90_dias) - Number(a.espera_p90_dias))
    .slice(0, 8);
  if (!sorted.length) {
    host.append(element('div', 'chart-empty', 'Não há grupos SISREG disponíveis para esta extração.'));
    return;
  }
  const maximum = Math.max(1, ...sorted.map((row) => Number(row.espera_p90_dias) || 0));
  sorted.forEach((row) => {
    const line = element('div', 'benchmark-bar-row');
    const name = element('span', 'benchmark-bar-name', row.procedimento);
    name.title = `${row.procedimento} · ${number.format(Number(row.solicitacoes_pendentes))} solicitações pendentes · mediana ${number.format(Number(row.espera_mediana_dias))} dias`;
    const track = element('span', 'benchmark-bar-track');
    const fill = element('span', 'benchmark-bar-fill');
    fill.style.width = `${Math.max(2, Number(row.espera_p90_dias) / maximum * 100)}%`;
    track.append(fill);
    line.append(name, track, element('span', 'benchmark-bar-value', `${number.format(Number(row.espera_p90_dias))} d`));
    host.append(line);
  });
  host.append(element('div', 'rank-foot', 'P90 da idade das solicitações ainda pendentes · passe o cursor para ver volume e mediana.'));
}

function renderMonthlyLineChart(hostId, rows, field, chartTitle, unit, color, minimumMaximum = 1) {
  const target = $(hostId);
  target.replaceChildren();
  const points = [...rows].sort((a, b) => a.ano_mes.localeCompare(b.ano_mes));
  if (!points.length) {
    target.append(element('div', 'chart-empty', 'Sem observações para o período.'));
    return;
  }
  const width = 760, height = 230, left = 48, right = 14, top = 13, bottom = 35;
  const plotW = width - left - right, plotH = height - top - bottom;
  const maxRaw = Math.max(minimumMaximum, ...points.map((row) => Number(row[field]) || 0));
  const max = Math.ceil(maxRaw / 4) * 4;
  const chart = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, class: 'benchmark-svg', role: 'img', 'aria-label': chartTitle });
  chart.append(svgNode('title', {}, chartTitle));
  for (let line = 0; line <= 4; line += 1) {
    const y = top + plotH * line / 4;
    const label = max * (1 - line / 4);
    chart.append(svgNode('line', { x1: left, y1: y, x2: width - right, y2: y, class: 'grid-line' }));
    chart.append(svgNode('text', { x: left - 7, y: y + 3, 'text-anchor': 'end', class: 'axis-label' }, `${number.format(label)}${unit}`));
  }
  const coords = points.map((row, index) => ({
    ...row,
    value: Number(row[field]) || 0,
    x: points.length > 1 ? left + plotW * index / (points.length - 1) : left + plotW / 2,
  })).map((point) => ({ ...point, y: top + plotH - point.value / max * plotH }));
  const path = coords.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
  chart.append(svgNode('path', { d: path, class: 'benchmark-series-line', stroke: color }));
  coords.forEach((point, index) => {
    const circle = svgNode('circle', { cx: point.x, cy: point.y, r: index === coords.length - 1 ? 4 : 3.2, class: 'benchmark-series-point', fill: color });
    circle.append(svgNode('title', {}, `${fullMonthLabel(point.ano_mes)}: ${decimal.format(point.value)}${unit}`));
    chart.append(circle);
    chart.append(svgNode('text', { x: point.x, y: height - 9, 'text-anchor': 'middle', class: 'axis-label' }, monthLabel(point.ano_mes)));
  });
  target.append(chart);
}

function renderBenchmarkOccupancy() {
  const rows = state.benchmark?.occupancy || [];
  renderMonthlyLineChart(
    'benchmark-occupancy-chart', rows, 'ocupacao_estimada_pct',
    'Ocupação estimada mensal em Alagoas em 2025', '%', '#177b73', 100,
  );
}

function renderBenchmarkCosts() {
  const host = $('benchmark-cost-chart');
  host.replaceChildren();
  const rows = [...(state.benchmark?.procedures || [])]
    .filter((row) => isKnownNumber(row.valor_aih_total))
    .sort((a, b) => Number(b.valor_aih_total) - Number(a.valor_aih_total));
  const top = rows.slice(0, 8);
  if (!top.length) {
    host.append(element('div', 'chart-empty', 'Sem valores de AIH disponíveis para este período.'));
    return;
  }
  const maximum = Math.max(1, ...top.map((row) => Number(row.valor_aih_total) || 0));
  top.forEach((row) => {
    const line = element('div', 'benchmark-bar-row');
    const procedureName = SIGTAP_DESCRIPTIONS[row.id_procedimento] || `SIGTAP ${row.id_procedimento}`;
    const label = element('span', 'benchmark-bar-name', procedureName);
    label.title = `${row.id_procedimento} · ${procedureName} · ${number.format(Number(row.volume_aih))} AIHs`;
    const track = element('span', 'benchmark-bar-track');
    const fill = element('span', 'benchmark-bar-fill');
    fill.style.width = `${Math.max(2, Number(row.valor_aih_total) / maximum * 100)}%`;
    track.append(fill);
    const value = element('span', 'benchmark-bar-value', currency.format(Number(row.valor_aih_total)));
    line.append(label, track, value);
    host.append(line);
  });
  host.append(element('div', 'rank-foot', `${number.format(rows.length)} códigos SIGTAP com AIH registrada · valor total do período.`));
}

function renderBenchmarkArrivals() {
  const host = $('benchmark-arrivals-chart');
  const rows = state.benchmark?.summary || [];
  renderMonthlyLineChart(
    'benchmark-arrivals-chart', rows, 'volume_aih',
    'AIHs por mês de admissão em Alagoas em 2025', '', '#4f7891', 1,
  );
}

function renderBenchmarkCapacity() {
  const host = $('benchmark-capacity-chart');
  host.replaceChildren();
  const rows = [...(state.benchmark?.capacity || [])].sort((a, b) => a.ano_mes.localeCompare(b.ano_mes));
  if (!rows.length) {
    host.append(element('div', 'chart-empty', 'Sem competências CNES disponíveis.'));
    return;
  }
  const maxTotal = Math.max(1, ...rows.map((row) => Number(row.total_leitos_sus) || 0));
  rows.forEach((row) => {
    const general = Number(row.leitos_gerais_sus) || 0;
    const icu = Number(row.leitos_uti_sus) || 0;
    const total = Number(row.total_leitos_sus) || general + icu;
    const line = element('div', 'benchmark-cost-row');
    line.append(element('span', 'benchmark-bar-name', monthLabel(row.ano_mes)));
    const track = element('span', 'benchmark-stacked-track');
    track.style.setProperty('--benchmark-relative-width', `${Math.max(2, total / maxTotal * 100)}%`);
    const generalSegment = element('i', 'cost-hospital');
    generalSegment.style.width = `${total ? general / total * 100 : 0}%`;
    const icuSegment = element('i', 'cost-opme');
    icuSegment.style.width = `${total ? icu / total * 100 : 0}%`;
    track.append(generalSegment, icuSegment);
    const value = element('span', 'benchmark-bar-value', number.format(total));
    line.title = `${monthLabel(row.ano_mes)}: ${number.format(general)} leitos gerais e ${number.format(icu)} leitos de UTI`;
    line.append(track, value);
    host.append(line);
  });
  const legend = element('div', 'benchmark-legend');
  [['cost-hospital', 'Leitos gerais SUS'], ['cost-opme', 'UTI SUS']].forEach(([className, label]) => {
    const item = element('span');
    const swatch = element('i', className);
    item.append(swatch, document.createTextNode(label));
    legend.append(item);
  });
  host.append(legend);
}

function renderBenchmark() {
  if (!state.benchmark) return;
  const rows = benchmarkRows();
  renderBenchmarkMetrics(rows);
  renderBenchmarkWait();
  renderBenchmarkOccupancy();
  renderBenchmarkCosts();
  renderBenchmarkArrivals();
  renderBenchmarkCapacity();
  renderBenchmarkMetadata();
  const manifestNote = state.benchmark.meta.manifestUnavailable
    ? ' Proveniência da carga indisponível.'
    : '';
  if (state.benchmark.meta.sihFallback) setBenchmarkNotice(
    `Exibindo agregados SIH/SUS de 2025: o MySQL ainda não retornou esses dados.${state.benchmark.meta.complementaryDataIncomplete ? ' Algumas fontes complementares do banco estão indisponíveis.' : ' CNES e SISREG seguem consultados no banco.'}${manifestNote}`,
    'warning',
  );
  else if (!rows.length) setBenchmarkNotice(`Sem AIHs de admissões neste período.${manifestNote}`, manifestNote ? 'warning' : 'ready');
  else setBenchmarkNotice(
    `Recorte por admissão: ${benchmarkLabelForPeriod()} · SIH processado até competência 12/2025; a coorte pode receber atualizações posteriores.${manifestNote}`,
    manifestNote ? 'warning' : 'ready',
  );
}

async function loadBenchmark() {
  const request = (state.benchmarkRequest || 0) + 1;
  state.benchmarkRequest = request;
  state.benchmarkLoading = true;
  const period = $('benchmark-period').value || 'all';
  setBenchmarkNotice('Consultando agregados públicos do SUS…', 'loading');
  try {
    const benchmark = await getJson(`${API.benchmark}?period=${encodeURIComponent(period)}`);
    if (request !== state.benchmarkRequest) return;
    state.benchmark = {
      summary: Array.isArray(benchmark.summary) ? benchmark.summary : [],
      procedures: Array.isArray(benchmark.procedures) ? benchmark.procedures : [],
      capacity: Array.isArray(benchmark.capacity) ? benchmark.capacity : [],
      occupancy: Array.isArray(benchmark.occupancy) ? benchmark.occupancy : [],
      waiting: Array.isArray(benchmark.waiting) ? benchmark.waiting : [],
      meta: benchmark.meta || {},
    };
    state.benchmarkError = '';
    if ($('benchmark-period').disabled) configureBenchmarkFilters();
    renderBenchmark();
  } catch (error) {
    if (request !== state.benchmarkRequest) return;
    state.benchmarkError = error.access ? 'Entre novamente para consultar os dados públicos.' : (error.message || 'Falha ao carregar os dados públicos.');
    setBenchmarkNotice(state.benchmarkError, 'error');
    ['benchmark-volume', 'benchmark-wait', 'benchmark-cost', 'benchmark-occupancy'].forEach((id) => { $(id).textContent = '—'; });
    ['benchmark-wait-chart', 'benchmark-occupancy-chart', 'benchmark-cost-chart', 'benchmark-arrivals-chart', 'benchmark-capacity-chart']
      .forEach((id) => { $(id).replaceChildren(element('div', 'chart-empty', 'Dados do benchmark indisponíveis.')); });
  } finally {
    if (request === state.benchmarkRequest) state.benchmarkLoading = false;
  }
}

async function refreshDashboard() {
  await Promise.all([loadDashboard(), loadBenchmark()]);
}

refreshDashboard();

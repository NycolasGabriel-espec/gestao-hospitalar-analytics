const API = {
  executive: '/api/executive?limit=1000',
  risk: '/api/risk?limit=1000',
};
const number = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 });
const $ = (id) => document.getElementById(id);
const state = { executive: [], risks: [], months: [], lastUpdated: null };
const SVG = 'http://www.w3.org/2000/svg';

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

function configureFilters() {
  const period = $('period-filter');
  const specialty = $('specialty-filter');
  period.replaceChildren();
  appendOption(period, 'all', 'Todas as competências');
  state.months.forEach((item) => appendOption(period, item.ano_mes, monthLabel(item.ano_mes)));
  period.value = state.months.length ? state.months[0].ano_mes : 'all';

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
  const specialty = $('specialty-filter').value;
  const byMonth = new Map();
  state.executive
    .filter((row) => specialty === 'all' || row.especialidade === specialty)
    .forEach((row) => byMonth.set(row.ano_mes, (byMonth.get(row.ano_mes) || 0) + (Number(row.volume_internacoes) || 0)));
  const points = [...byMonth.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-12);
  const host = $('trend-chart');
  host.replaceChildren();
  if (!points.length) {
    host.append(element('div', 'chart-empty', 'Ainda não há competências disponíveis para esta seleção.'));
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
  const chart = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, class: 'trend-svg', role: 'img', 'aria-label': 'Internações agregadas por competência nas coortes publicadas' });
  const title = svgNode('title', {}, 'Internações por competência, grupos publicados');
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
    host.append(element('div', 'chart-empty', 'Sem grupos publicados nesta competência.'));
    return;
  }
  const sorted = [...rows].sort((a, b) => Number(b.volume_internacoes || 0) - Number(a.volume_internacoes || 0)).slice(0, 6);
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
  const available = rows.filter((row) => isKnownNumber(row.taxa_mortalidade_pct))
    .sort((a, b) => Number(b.taxa_mortalidade_pct) - Number(a.taxa_mortalidade_pct)).slice(0, 5);
  if (!available.length) {
    host.append(element('p', 'outcome-empty', 'Indicador de óbito não disponível nesta seleção. A fonte pode ter desfechos ausentes.'));
    return;
  }
  const maximum = Math.max(1, ...available.map((row) => Number(row.taxa_mortalidade_pct)));
  available.forEach((row) => {
    const line = element('div', 'outcome-row');
    line.append(element('span', 'outcome-name', row.especialidade || 'Não classificada'));
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
  $('diagnosis-footnote').textContent = 'Exibindo até 10 coortes. Supressão mínima de 10 internações por grupo; isso reduz exposição, mas não garante anonimização.';
}

function render() {
  const rows = selectedRows();
  renderMetrics(rows);
  renderTrend();
  renderRanking(rows);
  renderOutcomes(rows);
  renderDiagnoses();
  if (!state.executive.length) setStatus('Sem dados publicados. Execute a extração PySUS, a transformação local e a carga autorizada para o Supabase.', 'error');
  else setStatus(`${number.format(rows.length)} grupos publicados na seleção. Dados agregados do SIH/SUS processados pelo pipeline PySUS.`);
}

async function loadDashboard() {
  const refresh = $('refresh-button');
  refresh.classList.add('is-loading');
  setStatus('Consultando os dados autorizados…', 'loading');
  try {
    const [executive, risks] = await Promise.all([
      getJson(API.executive), getJson(API.risk),
    ]);
    state.executive = executive;
    state.risks = risks;
    state.months = [...new Set(executive.map((item) => item.ano_mes).filter(Boolean))]
      .sort((a, b) => b.localeCompare(a)).map((ano_mes) => ({ ano_mes }));
    state.lastUpdated = new Date();
    configureFilters();
    render();
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

$('period-filter').addEventListener('change', render);
$('specialty-filter').addEventListener('change', render);
$('refresh-button').addEventListener('click', loadDashboard);
$('logout-button').addEventListener('click', async () => {
  $('logout-button').disabled = true;
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } });
  } finally {
    window.location.assign('../login.html');
  }
});

loadDashboard();

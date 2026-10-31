const BASE_HEADERS = {
  'Cache-Control': 's-maxage=60, stale-while-revalidate=300',
};

export function sendJson(res, status, body, headers = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  for (const [name, value] of Object.entries({ ...BASE_HEADERS, ...headers })) {
    res.setHeader(name, value);
  }
  res.end(JSON.stringify(body));
}

export function requireGet(req, res) {
  if (req.method === 'GET' || req.method === 'HEAD') return true;
  res.setHeader('Allow', 'GET, HEAD');
  sendJson(res, 405, { error: 'Método não permitido. Use GET.' });
  return false;
}

export function parseLimit(value, fallback = 100) {
  if (value === undefined) return fallback;
  const limit = Number(value);
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000) return null;
  return limit;
}

export async function queryView(view, { select, filters = {}, limit = 100 } = {}) {
  const url = process.env.SUPABASE_URL?.replace(/\/$/, '');
  const key = process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_KEY;
  if (!url || !key) {
    const error = new Error('SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY precisam estar configurados.');
    error.status = 503;
    throw error;
  }

  const params = new URLSearchParams({ select, limit: String(limit) });
  for (const [column, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(column, `eq.${value}`);
  }

  const response = await fetch(`${url}/rest/v1/${view}?${params}`, {
    headers: { apikey: key, Authorization: `Bearer ${key}` },
  });
  if (!response.ok) {
    const error = new Error('Não foi possível consultar os dados analíticos.');
    error.status = response.status >= 500 ? 502 : 400;
    error.details = (await response.text()).slice(0, 300);
    throw error;
  }
  return response.json();
}

export function handleError(res, error) {
  const status = error.status || 502;
  sendJson(res, status, {
    error: status === 503 ? error.message : 'Falha ao consultar o Supabase.',
    ...(error.details ? { details: error.details } : {}),
  });
}

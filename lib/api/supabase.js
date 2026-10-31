const BASE_HEADERS = {
  'Cache-Control': 's-maxage=60, stale-while-revalidate=300',
};

export function sendJson(res, status, body, headers = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  const currentCacheControl = res.getHeader?.('Cache-Control');
  for (const [name, value] of Object.entries({ ...BASE_HEADERS, ...(currentCacheControl ? { 'Cache-Control': currentCacheControl } : {}), ...headers })) {
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

export async function queryView(view, { select, filters = {}, limit = 100, accessToken } = {}) {
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
    headers: { apikey: key, Authorization: `Bearer ${accessToken || key}` },
  });
  if (!response.ok) {
    const error = new Error('Não foi possível consultar os dados analíticos.');
    error.status = response.status >= 500 ? 502 : 400;
    error.details = (await response.text()).slice(0, 300);
    throw error;
  }
  return response.json();
}

export async function requireAuth(req, res) {
  const url = process.env.SUPABASE_URL?.replace(/\/$/, '');
  const key = process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_KEY;
  const authorization = req.headers.authorization || '';
  const token = authorization.match(/^Bearer\s+(.+)$/i)?.[1];
  if (!url || !key) {
    sendJson(res, 503, { error: 'SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY precisam estar configurados.' });
    return null;
  }
  res.setHeader('Cache-Control', 'private, no-store');
  if (!token) {
    sendJson(res, 401, { error: 'Autenticação necessária.' });
    return null;
  }
  try {
    const response = await fetch(`${url}/auth/v1/user`, {
      headers: { apikey: key, Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      sendJson(res, 401, { error: 'Sessão inválida ou expirada.' });
      return null;
    }
    return { user: await response.json(), accessToken: token };
  } catch {
    sendJson(res, 502, { error: 'Não foi possível validar a sessão.' });
    return null;
  }
}

export function handleError(res, error) {
  const status = error.status || 502;
  sendJson(res, status, {
    error: status === 503 ? error.message : 'Falha ao consultar o Supabase.',
    ...(error.details ? { details: error.details } : {}),
  });
}

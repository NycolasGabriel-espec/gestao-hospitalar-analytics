const ACCESS_COOKIE = 'hospital_analytics_access';
const REFRESH_COOKIE = 'hospital_analytics_refresh';
const COOKIE_BASE = `Path=/api; HttpOnly; SameSite=Strict${process.env.NODE_ENV === 'production' ? '; Secure' : ''}`;
const API_HEADERS = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' };

export function sendJson(res, status, body, headers = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  for (const [name, value] of Object.entries({ ...API_HEADERS, ...headers })) {
    res.setHeader(name, value);
  }
  res.end(JSON.stringify(body));
}

function isPublicApiKey(key) {
  if (key.startsWith('sb_publishable_')) return true;
  const parts = key.split('.');
  if (parts.length !== 3) return false;
  try {
    const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
    return payload.role === 'anon';
  } catch {
    return false;
  }
}

export function getSupabaseConfig() {
  const configuredUrl = process.env.SUPABASE_URL?.replace(/\/$/, '');
  const key = process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_KEY;
  let parsedUrl;
  try { parsedUrl = new URL(configuredUrl); } catch { parsedUrl = null; }

  if (
    !parsedUrl || !['https:', 'http:'].includes(parsedUrl.protocol) ||
    parsedUrl.username || parsedUrl.password || parsedUrl.search || parsedUrl.hash ||
    !['', '/'].includes(parsedUrl.pathname) || !key || !isPublicApiKey(key)
  ) {
    const error = new Error('A URL e a chave publishable/anônima do Supabase precisam estar configuradas.');
    error.status = 503;
    throw error;
  }
  if (parsedUrl.protocol === 'http:' && !['localhost', '127.0.0.1'].includes(parsedUrl.hostname)) {
    const error = new Error('A URL do Supabase precisa usar HTTPS.');
    error.status = 503;
    throw error;
  }
  return { url: parsedUrl.origin, key };
}

export function requireGet(req, res) {
  if (req.method === 'GET') return true;
  res.setHeader('Allow', 'GET');
  sendJson(res, 405, { error: 'Método não permitido. Use GET.' });
  return false;
}

export function requirePost(req, res) {
  if (req.method === 'POST') return true;
  res.setHeader('Allow', 'POST');
  sendJson(res, 405, { error: 'Método não permitido. Use POST.' });
  return false;
}

export function isSameOriginRequest(req) {
  const origin = req.headers.origin;
  const host = req.headers.host;
  if (!origin || !host) return false;
  try {
    const parsed = new URL(origin);
    const forwardedProto = String(req.headers['x-forwarded-proto'] || '').split(',')[0].trim();
    const expectedProtocol = forwardedProto || (process.env.NODE_ENV === 'production' ? 'https' : parsed.protocol.replace(':', ''));
    return parsed.host.toLowerCase() === String(host).toLowerCase() && parsed.protocol === `${expectedProtocol}:`;
  } catch {
    return false;
  }
}

export function readJsonBody(req) {
  const contentType = String(req.headers['content-type'] || '').split(';')[0].trim().toLowerCase();
  if (contentType !== 'application/json') return null;
  const length = Number(req.headers['content-length'] || 0);
  if (length > 8192) return null;
  try {
    const serialized = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    if (Buffer.byteLength(serialized || '', 'utf8') > 8192) return null;
    const body = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    return body && typeof body === 'object' && !Array.isArray(body) ? body : null;
  } catch {
    return null;
  }
}

export function getSessionTokens(req) {
  const cookies = String(req.headers.cookie || '').split(';');
  const values = new Map();
  for (const part of cookies) {
    const separator = part.indexOf('=');
    if (separator < 0) continue;
    const name = part.slice(0, separator).trim();
    const value = part.slice(separator + 1).trim();
    try { values.set(name, decodeURIComponent(value)); } catch { values.set(name, ''); }
  }
  return {
    accessToken: values.get(ACCESS_COOKIE) || '',
    refreshToken: values.get(REFRESH_COOKIE) || '',
  };
}

function validToken(token) {
  return typeof token === 'string' && token.length >= 20 && token.length <= 4096 && /^[A-Za-z0-9._~-]+$/.test(token);
}

export function setSessionCookies(res, { accessToken, refreshToken, expiresIn = 3600 }) {
  if (!validToken(accessToken) || !validToken(refreshToken)) {
    throw new Error('Sessão inválida.');
  }
  const age = Math.min(86400, Math.max(60, Number(expiresIn) || 3600));
  res.setHeader('Set-Cookie', [
    `${ACCESS_COOKIE}=${encodeURIComponent(accessToken)}; ${COOKIE_BASE}; Max-Age=${age}`,
    `${REFRESH_COOKIE}=${encodeURIComponent(refreshToken)}; ${COOKIE_BASE}`,
  ]);
}

export function clearSessionCookies(res) {
  res.setHeader('Set-Cookie', [
    `${ACCESS_COOKIE}=; ${COOKIE_BASE}; Max-Age=0`,
    `${REFRESH_COOKIE}=; ${COOKIE_BASE}; Max-Age=0`,
  ]);
}

export async function getAuthUser(accessToken) {
  if (!validToken(accessToken)) return null;
  const { url, key } = getSupabaseConfig();
  const response = await fetch(`${url}/auth/v1/user`, {
    headers: { apikey: key, Authorization: `Bearer ${accessToken}` },
    signal: AbortSignal.timeout(7000),
    redirect: 'error',
  });
  if (!response.ok) return null;
  return response.json();
}

export function isAuthorizedUser(user) {
  return user?.app_metadata?.hospital_analytics_access === true;
}

export function parseLimit(value, fallback = 100) {
  if (value === undefined) return fallback;
  const limit = Number(value);
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000) return null;
  return limit;
}

export async function queryView(view, { select, filters = {}, limit = 100, accessToken } = {}) {
  let config;
  try { config = getSupabaseConfig(); } catch (error) { throw error; }
  if (!validToken(accessToken)) {
    const error = new Error('Autenticação necessária.');
    error.status = 401;
    throw error;
  }

  const params = new URLSearchParams({ select, limit: String(limit) });
  for (const [column, rawValue] of Object.entries(filters)) {
    const value = String(rawValue);
    if (!/^[a-z_]+$/.test(column) || !/^[\p{L}\p{N} _./&+-]{1,80}$/u.test(value)) {
      const error = new Error('Filtro inválido.');
      error.status = 400;
      throw error;
    }
    params.set(column, `eq.${value}`);
  }

  const response = await fetch(`${config.url}/rest/v1/${view}?${params}`, {
    headers: { apikey: config.key, Authorization: `Bearer ${accessToken}` },
    signal: AbortSignal.timeout(10000),
    redirect: 'error',
  });
  if (!response.ok) {
    const error = new Error('Não foi possível consultar os dados analíticos.');
    error.status = response.status >= 500 ? 502 : 400;
    throw error;
  }
  return response.json();
}

async function refreshSession(refreshToken) {
  const { url, key } = getSupabaseConfig();
  const response = await fetch(`${url}/auth/v1/token?grant_type=refresh_token`, {
    method: 'POST',
    headers: { apikey: key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
    signal: AbortSignal.timeout(7000),
    redirect: 'error',
  });
  if (!response.ok) return null;
  return response.json();
}

export async function requireAuth(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  const { accessToken, refreshToken } = getSessionTokens(req);
  if (!accessToken && !refreshToken) {
    sendJson(res, 401, { error: 'Autenticação necessária.' });
    return null;
  }

  try {
    let token = accessToken;
    let user = token ? await getAuthUser(token) : null;
    if (!user && refreshToken && validToken(refreshToken)) {
      const session = await refreshSession(refreshToken);
      if (session?.access_token && session?.refresh_token) {
        token = session.access_token;
        user = await getAuthUser(token);
        if (user) setSessionCookies(res, session);
      }
    }

    if (!user) {
      clearSessionCookies(res);
      sendJson(res, 401, { error: 'Sessão inválida ou expirada.' });
      return null;
    }
    if (!isAuthorizedUser(user)) {
      clearSessionCookies(res);
      sendJson(res, 403, { error: 'Esta conta não tem acesso aos dados analíticos.' });
      return null;
    }
    return { user, accessToken: token };
  } catch {
    sendJson(res, 502, { error: 'Não foi possível validar a sessão.' });
    return null;
  }
}

export function handleError(res, error) {
  const status = [400, 401, 403, 503].includes(error.status) ? error.status : 502;
  sendJson(res, status, {
    error: status === 503 ? error.message : status === 400 ? 'Filtro inválido.' : 'Falha ao consultar o Supabase.',
  });
}

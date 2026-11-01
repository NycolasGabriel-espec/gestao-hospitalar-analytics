import { createPool } from 'mysql2/promise';
import {
  createHash,
  createHmac,
  randomBytes,
  scrypt as scryptCallback,
  timingSafeEqual,
} from 'node:crypto';
import { promisify } from 'node:util';

const COOKIE_NAME = 'hospital_analytics_session';
const SESSION_SECONDS = 12 * 60 * 60;
const COOKIE_BASE = `Path=/api; HttpOnly; SameSite=Strict${process.env.NODE_ENV === 'production' ? '; Secure' : ''}`;
const API_HEADERS = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' };
const scrypt = promisify(scryptCallback);

const VIEW_COLUMNS = {
  vw_painel_executivo_mensal: new Set([
    'ano_mes', 'ano', 'mes', 'nome_mes', 'especialidade', 'volume_internacoes',
    'receita_total', 'custo_total', 'custo_opme', 'margem_contribuicao', 'margem_pct',
    'tmp_medio', 'taxa_readmissao_pct', 'taxa_mortalidade_pct',
  ]),
  vw_eficiencia_leitos_setor: new Set([
    'ano_mes', 'id_leito', 'tipo_acomodacao', 'setor_hospitalar', 'leitos_operacionais',
    'total_admissoes', 'dias_permanencia_coorte', 'dias_uti_reportados_coorte',
    'leitos_dia_teoricos', 'taxa_ocupacao_pct', 'admissoes_por_leito_aproximado',
  ]),
  vw_detalhe_clinico_risco: new Set([
    'ano_mes', 'cid_10', 'descricao_cid', 'grau_severidade', 'especialidade',
    'descricao_procedimento', 'faixa_etaria', 'volume_internacoes', 'tmp_medio',
    'custo_medio', 'taxa_mortalidade_pct', 'taxa_readmissao_pct',
  ]),
  vw_dim_procedimento: new Set([
    'id_procedimento', 'descricao_procedimento', 'especialidade', 'complexidade',
    'tmp_protocolo_previsto',
  ]),
  vw_dim_diagnostico: new Set(['cid_10', 'descricao_cid', 'capitulo_cid', 'grau_severidade']),
  vw_dim_setor_leito: new Set(['id_leito', 'tipo_acomodacao', 'setor_hospitalar', 'leitos_operacionais']),
  vw_dim_tempo: new Set(['ano_mes', 'ano', 'mes', 'nome_mes']),
};

const VIEW_FILTERS = {
  vw_painel_executivo_mensal: new Set(['ano_mes', 'especialidade']),
  vw_eficiencia_leitos_setor: new Set(['ano_mes', 'id_leito']),
  vw_detalhe_clinico_risco: new Set(['ano_mes', 'cid_10', 'especialidade', 'grau_severidade']),
  vw_dim_procedimento: new Set(['id_procedimento', 'especialidade']),
  vw_dim_diagnostico: new Set(['cid_10', 'grau_severidade']),
  vw_dim_setor_leito: new Set(['id_leito']),
  vw_dim_tempo: new Set(['ano_mes', 'ano', 'mes']),
};

let pool;

export function sendJson(res, status, body, headers = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  for (const [name, value] of Object.entries({ ...API_HEADERS, ...headers })) {
    res.setHeader(name, value);
  }
  res.end(JSON.stringify(body));
}

export function getPool() {
  if (pool) return pool;
  const configuredUrl = process.env.MYSQL_URL;
  let parsed;
  try { parsed = new URL(configuredUrl); } catch { parsed = null; }

  if (
    !parsed || parsed.protocol !== 'mysql:' || !parsed.hostname || !parsed.username ||
    !parsed.password || parsed.pathname.length < 2 || parsed.search || parsed.hash
  ) {
    const error = new Error('Configure MYSQL_URL com uma conexão MySQL válida.');
    error.status = 503;
    throw error;
  }
  if (decodeURIComponent(parsed.username).toLowerCase() === 'root') {
    const error = new Error('MYSQL_URL da aplicação precisa usar a conta restrita dashboard_app.');
    error.status = 503;
    throw error;
  }

  const localHost = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  const tlsEnabled = process.env.MYSQL_TLS === 'true';
  if (process.env.NODE_ENV === 'production' && !tlsEnabled) {
    const error = new Error('MYSQL_TLS=true é obrigatório em produção.');
    error.status = 503;
    throw error;
  }
  if (!tlsEnabled && !localHost) {
    const error = new Error('Conexões MySQL remotas precisam usar TLS.');
    error.status = 503;
    throw error;
  }

  const connectionLimit = Number(process.env.MYSQL_CONNECTION_LIMIT || 3);
  if (!Number.isInteger(connectionLimit) || connectionLimit < 1 || connectionLimit > 10) {
    const error = new Error('MYSQL_CONNECTION_LIMIT deve ficar entre 1 e 10.');
    error.status = 503;
    throw error;
  }

  pool = createPool({
    host: parsed.hostname,
    port: Number(parsed.port || 3306),
    user: decodeURIComponent(parsed.username),
    password: decodeURIComponent(parsed.password),
    database: decodeURIComponent(parsed.pathname.slice(1)),
    ssl: tlsEnabled ? {
      rejectUnauthorized: true,
      verifyIdentity: true,
      ...(process.env.MYSQL_SSL_CA ? { ca: process.env.MYSQL_SSL_CA } : {}),
    } : undefined,
    waitForConnections: true,
    connectionLimit,
    queueLimit: 30,
    connectTimeout: 10000,
    enableKeepAlive: true,
    decimalNumbers: true,
    timezone: 'Z',
  });
  return pool;
}

export async function checkDatabase() {
  await getPool().query('SELECT 1');
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

export function getSessionToken(req) {
  for (const part of String(req.headers.cookie || '').split(';')) {
    const separator = part.indexOf('=');
    if (separator < 0 || part.slice(0, separator).trim() !== COOKIE_NAME) continue;
    try {
      const token = decodeURIComponent(part.slice(separator + 1).trim());
      return /^[A-Za-z0-9_-]{40,60}$/.test(token) ? token : '';
    } catch {
      return '';
    }
  }
  return '';
}

export function setSessionCookie(res, token) {
  if (typeof token !== 'string' || !/^[A-Za-z0-9_-]{40,60}$/.test(token)) {
    throw new Error('Sessão inválida.');
  }
  res.setHeader('Set-Cookie', `${COOKIE_NAME}=${encodeURIComponent(token)}; ${COOKIE_BASE}; Max-Age=${SESSION_SECONDS}`);
}

export function clearSessionCookie(res) {
  res.setHeader('Set-Cookie', `${COOKIE_NAME}=; ${COOKIE_BASE}; Max-Age=0`);
}

export function hashSessionToken(token) {
  return createHash('sha256').update(token).digest();
}

export async function createSession(userId) {
  const token = randomBytes(32).toString('base64url');
  await getPool().execute(
    'INSERT INTO auth_sessions (session_hash, user_id, expires_at) VALUES (?, ?, DATE_ADD(UTC_TIMESTAMP(), INTERVAL 12 HOUR))',
    [hashSessionToken(token), userId],
  );
  return token;
}

export async function requireAuth(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  const token = getSessionToken(req);
  if (!token) {
    clearSessionCookie(res);
    sendJson(res, 401, { error: 'Autenticação necessária.' });
    return null;
  }

  try {
    const [rows] = await getPool().execute(
      `SELECT u.id, u.email, u.hospital_analytics_access
       FROM auth_sessions s
       JOIN app_users u ON u.id = s.user_id
       WHERE s.session_hash = ? AND s.expires_at > UTC_TIMESTAMP()
       LIMIT 1`,
      [hashSessionToken(token)],
    );
    const user = rows[0];
    if (!user) {
      clearSessionCookie(res);
      sendJson(res, 401, { error: 'Sessão inválida ou expirada.' });
      return null;
    }
    if (Number(user.hospital_analytics_access) !== 1) {
      clearSessionCookie(res);
      sendJson(res, 403, { error: 'Esta conta não está habilitada para acessar os dados.' });
      return null;
    }
    return { user, token, sessionHash: hashSessionToken(token) };
  } catch {
    sendJson(res, 502, { error: 'Não foi possível validar a sessão.' });
    return null;
  }
}

export function parseLimit(value, fallback = 100) {
  if (value === undefined) return fallback;
  const limit = Number(value);
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000) return null;
  return limit;
}

export async function queryView(view, { select, filters = {}, limit = 100 } = {}) {
  const columns = VIEW_COLUMNS[view];
  if (!columns || typeof select !== 'string') {
    const error = new Error('View analítica inválida.');
    error.status = 400;
    throw error;
  }
  const selected = select.split(',').map((column) => column.trim());
  if (!selected.length || selected.some((column) => !columns.has(column))) {
    const error = new Error('Colunas analíticas inválidas.');
    error.status = 400;
    throw error;
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 1000) {
    const error = new Error('Limite inválido.');
    error.status = 400;
    throw error;
  }

  const clauses = [];
  const values = [];
  for (const [column, rawValue] of Object.entries(filters)) {
    const value = String(rawValue);
    if (
      !VIEW_FILTERS[view].has(column) || !/^[\p{L}\p{N} _./&+-]{1,80}$/u.test(value)
    ) {
      const error = new Error('Filtro inválido.');
      error.status = 400;
      throw error;
    }
    clauses.push(`\`${column}\` = ?`);
    values.push(value);
  }

  const order = view === 'vw_detalhe_clinico_risco' ? ' ORDER BY `volume_internacoes` DESC, `ano_mes` DESC, `cid_10`' : '';
  const sql = `SELECT ${selected.map((column) => `\`${column}\``).join(', ')} FROM \`${view}\`${clauses.length ? ` WHERE ${clauses.join(' AND ')}` : ''}${order} LIMIT ?`;
  const [rows] = await getPool().execute(sql, [...values, limit]);
  return rows;
}

export async function hashPassword(password) {
  if (typeof password !== 'string' || password.length < 8 || password.length > 1024) {
    throw new Error('A senha deve ter entre 8 e 1024 caracteres.');
  }
  const salt = randomBytes(16);
  const key = await scrypt(password, salt, 64, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
  return `scrypt$16384$8$1$${salt.toString('base64url')}$${key.toString('base64url')}`;
}

export async function verifyPassword(password, storedHash) {
  if (typeof password !== 'string' || typeof storedHash !== 'string') return false;
  const [algorithm, n, r, p, saltEncoded, keyEncoded, ...extra] = storedHash.split('$');
  if (algorithm !== 'scrypt' || n !== '16384' || r !== '8' || p !== '1' || !saltEncoded || !keyEncoded || extra.length) return false;
  try {
    const salt = Buffer.from(saltEncoded, 'base64url');
    const expected = Buffer.from(keyEncoded, 'base64url');
    if (salt.length !== 16 || expected.length !== 64) return false;
    const actual = await scrypt(password, salt, expected.length, { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
    return timingSafeEqual(actual, expected);
  } catch {
    return false;
  }
}

export function rateLimitDigests(email, ipAddress) {
  const secret = process.env.AUTH_RATE_LIMIT_SECRET;
  if (!secret || secret.length < 32) {
    const error = new Error('Configure AUTH_RATE_LIMIT_SECRET com pelo menos 32 caracteres.');
    error.status = 503;
    throw error;
  }
  const emailDigest = createHmac('sha256', secret).update(email.trim().toLowerCase()).digest();
  const ipDigest = createHmac('sha256', secret).update(ipAddress || 'unknown').digest();
  return { emailDigest, ipDigest };
}

export function getClientIp(req) {
  const forwarded = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  return forwarded || String(req.socket?.remoteAddress || 'unknown');
}

export async function isRateLimited(email, ipAddress) {
  const { emailDigest, ipDigest } = rateLimitDigests(email, ipAddress);
  const [rows] = await getPool().execute(
    `SELECT COUNT(*) AS attempts
     FROM auth_login_attempts
     WHERE succeeded = 0
       AND attempted_at >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 15 MINUTE)
       AND (email_digest = ? OR ip_digest = ?)`,
    [emailDigest, ipDigest],
  );
  return Number(rows[0]?.attempts || 0) >= 10;
}

export async function recordLoginAttempt(email, ipAddress, succeeded) {
  const { emailDigest, ipDigest } = rateLimitDigests(email, ipAddress);
  await getPool().execute(
    'INSERT INTO auth_login_attempts (email_digest, ip_digest, succeeded) VALUES (?, ?, ?)',
    [emailDigest, ipDigest, succeeded ? 1 : 0],
  );
  await getPool().execute(
    'DELETE FROM auth_login_attempts WHERE attempted_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR) LIMIT 1000',
  );
}

export function handleError(res, error) {
  const status = [400, 401, 403, 429, 503].includes(error.status) ? error.status : 502;
  sendJson(res, status, {
    error: status === 400 ? 'Filtro inválido.' : status === 401 ? 'Autenticação necessária.' :
      status === 403 ? 'Esta conta não está habilitada para acessar os dados.' :
        status === 429 ? 'Muitas tentativas. Aguarde e tente novamente.' :
          status === 503 ? error.message : 'Falha ao consultar o banco de dados.',
  });
}

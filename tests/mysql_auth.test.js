import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';

const envKeys = ['MYSQL_URL', 'MYSQL_TLS', 'MYSQL_SSL_CA', 'MYSQL_CONNECTION_LIMIT', 'AUTH_RATE_LIMIT_SECRET', 'NODE_ENV'];
const originalEnv = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]));
let moduleNumber = 0;

function configure(overrides = {}) {
  const settings = {
    MYSQL_URL: 'mysql://dashboard_app:test-password@database.example:3306/analytics',
    MYSQL_TLS: 'true',
    AUTH_RATE_LIMIT_SECRET: 'a-test-only-secret-with-more-than-32-characters',
    NODE_ENV: 'production',
    ...overrides,
  };
  for (const key of envKeys) {
    if (settings[key] === undefined) delete process.env[key];
    else process.env[key] = settings[key];
  }
}

async function freshModule(overrides) {
  configure(overrides);
  return import(`../lib/api/mysql.js?test=${moduleNumber++}`);
}

function response() {
  return {
    headers: {},
    setHeader(name, value) { this.headers[name] = value; },
    end(body) { this.body = JSON.parse(body); },
  };
}

afterEach(() => {
  for (const key of envKeys) {
    if (originalEnv[key] === undefined) delete process.env[key];
    else process.env[key] = originalEnv[key];
  }
});

test('database configuration rejects missing credentials, root and plaintext remote connections', async () => {
  for (const overrides of [
    { MYSQL_URL: undefined },
    { MYSQL_URL: 'mysql://root:test-password@database.example:3306/analytics' },
    { MYSQL_TLS: 'false' },
  ]) {
    const database = await freshModule(overrides);
    assert.throws(() => database.getPool(), (error) => error.status === 503);
  }
});

test('remote pool validates both the certificate chain and server identity', async () => {
  const database = await freshModule({ MYSQL_CONNECTION_LIMIT: '2' });
  const pool = database.getPool();
  try {
    const config = pool.pool.config.connectionConfig;
    assert.equal(config.ssl.rejectUnauthorized, true);
    assert.equal(config.ssl.verifyIdentity, true);
    assert.equal(pool.pool.config.connectionLimit, 2);
    assert.equal(pool.pool.config.maxIdle, 1);
    assert.equal(pool.pool.config.idleTimeout, 5000);
    assert.equal(pool.listenerCount('release'), 1);
  } finally {
    await pool.end();
  }
});

test('passwords are salted and only the correct password verifies', async () => {
  const database = await freshModule();
  const password = 'synthetic-password-for-auth-test';
  const firstHash = await database.hashPassword(password);
  const secondHash = await database.hashPassword(password);
  assert.notEqual(firstHash, secondHash);
  assert.equal(await database.verifyPassword(password, firstHash), true);
  assert.equal(await database.verifyPassword('incorrect-password', firstHash), false);
  assert.equal(await database.verifyPassword(password, 'invalid-stored-hash'), false);
});

test('queries bind filter values and reject unapproved tables and columns', async () => {
  const database = await freshModule();
  const pool = database.getPool();
  const calls = [];
  pool.execute = async (...args) => { calls.push(args); return [[{ ano_mes: '2026-10' }]]; };
  try {
    const data = await database.queryView('vw_painel_executivo_mensal', {
      select: 'ano_mes,volume_internacoes', filters: { especialidade: 'Clínica Médica' }, limit: 25,
    });
    assert.equal(data.length, 1);
    assert.match(calls[0][0], /WHERE `especialidade` = \? LIMIT \?/);
    assert.deepEqual(calls[0][1], ['Clínica Médica', 25]);
    await assert.rejects(database.queryView('app_users', { select: 'password_hash' }));
    await assert.rejects(database.queryView('vw_dim_tempo', { select: 'password_hash' }));
    assert.equal(calls.length, 1);
    await database.queryView('vw_detalhe_clinico_risco', { select: 'cid_10,volume_internacoes', filters: { ano_mes: '2025-12' }, limit: 10 });
    assert.match(calls[1][0], /WHERE `ano_mes` = \? ORDER BY `volume_internacoes` DESC/);
    assert.deepEqual(calls[1][1], ['2025-12', 10]);
  } finally {
    await pool.end();
  }
});

test('login issues a hashed database session only for an authorized account', async () => {
  configure();
  const database = await import('../lib/api/mysql.js');
  const { default: login } = await import('../api/auth/login.js');
  const pool = database.getPool();
  const password = 'synthetic-password-for-login-test';
  const user = { id: 'test-user-id', email: 'test@example.org', password_hash: await database.hashPassword(password), hospital_analytics_access: 1 };
  const sessionInserts = [];
  pool.execute = async (sql, values) => {
    if (sql.includes('COUNT(*)')) return [[{ attempts: 0 }]];
    if (sql.includes('FROM app_users')) return [[user]];
    if (sql.includes('INSERT INTO auth_sessions')) sessionInserts.push(values);
    return [{ affectedRows: 1 }];
  };
  const req = {
    method: 'POST',
    headers: { origin: 'https://app.example', host: 'app.example', 'x-forwarded-proto': 'https', 'content-type': 'application/json' },
    body: { email: user.email, password },
  };
  try {
    const accepted = response();
    await login(req, accepted);
    assert.equal(accepted.statusCode, 200);
    assert.deepEqual(accepted.body, { status: 'ok' });
    assert.match(accepted.headers['Set-Cookie'], /HttpOnly; SameSite=Strict; Secure/);
    const token = accepted.headers['Set-Cookie'].split(';')[0].split('=')[1];
    assert.deepEqual(sessionInserts[0][0], database.hashSessionToken(token));
    assert.equal(sessionInserts[0][0].length, 32);

    user.hospital_analytics_access = 0;
    const denied = response();
    await login(req, denied);
    assert.equal(denied.statusCode, 403);
    assert.equal(sessionInserts.length, 1);

    const wrongPassword = response();
    await login({ ...req, body: { email: user.email, password: 'incorrect-password' } }, wrongPassword);
    assert.equal(wrongPassword.statusCode, 401);
    assert.equal(sessionInserts.length, 1);
  } finally {
    await pool.end();
  }
});

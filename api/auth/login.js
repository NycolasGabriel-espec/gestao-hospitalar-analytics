import {
  clearSessionCookie,
  createSession,
  getClientIp,
  getPool,
  handleError,
  isRateLimited,
  isSameOriginRequest,
  recordLoginAttempt,
  readJsonBody,
  requirePost,
  sendJson,
  setSessionCookie,
  verifyPassword,
} from '../../lib/api/mysql.js';

// Hash fictício para equalizar o custo de scrypt quando o e-mail não existe.
const DUMMY_PASSWORD_HASH = 'scrypt$16384$8$1$ABEiM0RVZneImaq7zN3u_w$d-TK2Ho2RhCYBR5F4v7ZTBfMI_YsN9gbIJbrdUj_4vuWcf4MAJweW7x7L5tgJQXH3PWLxJx6kbEmniEkdSLyZQ';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!requirePost(req, res)) return;
  if (!isSameOriginRequest(req)) return sendJson(res, 403, { error: 'Requisição não autorizada.' });

  const body = readJsonBody(req);
  const email = typeof body?.email === 'string' ? body.email.trim().toLowerCase() : '';
  const password = typeof body?.password === 'string' ? body.password : '';
  if (!email || email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || !password || password.length > 1024) {
    return sendJson(res, 400, { error: 'Informe um e-mail e uma senha válidos.' });
  }

  const ipAddress = getClientIp(req);
  try {
    if (await isRateLimited(email, ipAddress)) {
      return sendJson(res, 429, { error: 'Muitas tentativas. Aguarde e tente novamente.' });
    }

    const [rows] = await getPool().execute(
      'SELECT id, email, password_hash, hospital_analytics_access FROM app_users WHERE email = ? LIMIT 1',
      [email],
    );
    const user = rows[0];
    const passwordMatches = await verifyPassword(
      password,
      user?.password_hash || DUMMY_PASSWORD_HASH,
    );
    const authorized = Boolean(user) && passwordMatches && Number(user.hospital_analytics_access) === 1;
    await recordLoginAttempt(email, ipAddress, authorized);

    if (!authorized) {
      clearSessionCookie(res);
      return sendJson(res, 401, { error: 'Não foi possível entrar. Confira suas credenciais.' });
    }

    const token = await createSession(user.id);
    setSessionCookie(res, token);
    return sendJson(res, 200, { status: 'ok' });
  } catch (error) {
    handleError(res, error);
  }
}

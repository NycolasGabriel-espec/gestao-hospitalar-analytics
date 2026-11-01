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
    const passwordMatches = user ? await verifyPassword(password, user.password_hash) : false;
    const authorized = passwordMatches && Number(user.hospital_analytics_access) === 1;
    await recordLoginAttempt(email, ipAddress, authorized);

    if (!passwordMatches) {
      clearSessionCookie(res);
      return sendJson(res, 401, { error: 'Não foi possível entrar. Confira suas credenciais.' });
    }
    if (!authorized) {
      clearSessionCookie(res);
      return sendJson(res, 403, { error: 'Esta conta não está habilitada para acessar os dados.' });
    }

    const token = await createSession(user.id);
    setSessionCookie(res, token);
    return sendJson(res, 200, { status: 'ok' });
  } catch (error) {
    handleError(res, error);
  }
}

import {
  clearSessionCookie,
  getPool,
  getSessionToken,
  hashSessionToken,
  isSameOriginRequest,
  requirePost,
  sendJson,
} from '../../lib/api/mysql.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!requirePost(req, res)) return;
  if (!isSameOriginRequest(req)) return sendJson(res, 403, { error: 'Requisição não autorizada.' });

  const token = getSessionToken(req);
  if (token) {
    try {
      await getPool().execute('DELETE FROM auth_sessions WHERE session_hash = ?', [hashSessionToken(token)]);
    } catch {
      // A limpeza do cookie local deve ocorrer mesmo se a conexão MySQL estiver indisponível.
    }
  }
  clearSessionCookie(res);
  return sendJson(res, 200, { status: 'ok' });
}

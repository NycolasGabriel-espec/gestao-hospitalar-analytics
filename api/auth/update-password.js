import { randomBytes } from 'node:crypto';
import {
  getPool,
  hashPassword,
  hashSessionToken,
  isSameOriginRequest,
  requireAuth,
  requirePost,
  readJsonBody,
  sendJson,
  setSessionCookie,
} from '../../lib/api/mysql.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!requirePost(req, res)) return;
  if (!isSameOriginRequest(req)) return sendJson(res, 403, { error: 'Requisição não autorizada.' });

  const body = readJsonBody(req);
  const password = typeof body?.password === 'string' ? body.password : '';
  if (password.length < 8 || password.length > 1024) {
    return sendJson(res, 400, { error: 'A senha deve ter entre 8 e 1024 caracteres.' });
  }

  const session = await requireAuth(req, res);
  if (!session) return;

  let connection;
  try {
    const passwordHash = await hashPassword(password);
    const token = randomBytes(32).toString('base64url');
    const tokenHash = hashSessionToken(token);
    connection = await getPool().getConnection();
    await connection.beginTransaction();
    await connection.execute('UPDATE app_users SET password_hash = ? WHERE id = ?', [passwordHash, session.user.id]);
    await connection.execute('DELETE FROM auth_sessions WHERE user_id = ?', [session.user.id]);
    await connection.execute(
      'INSERT INTO auth_sessions (session_hash, user_id, expires_at) VALUES (?, ?, DATE_ADD(UTC_TIMESTAMP(), INTERVAL 12 HOUR))',
      [tokenHash, session.user.id],
    );
    await connection.commit();
    setSessionCookie(res, token);
    return sendJson(res, 200, { status: 'ok' });
  } catch {
    if (connection) await connection.rollback().catch(() => {});
    return sendJson(res, 502, { error: 'Não foi possível atualizar a senha agora.' });
  } finally {
    connection?.release();
  }
}

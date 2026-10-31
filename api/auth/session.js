import {
  clearSessionCookies,
  getAuthUser,
  isAuthorizedUser,
  isSameOriginRequest,
  readJsonBody,
  requirePost,
  sendJson,
  setSessionCookies,
} from '../../lib/api/supabase.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!requirePost(req, res)) return;
  if (!isSameOriginRequest(req)) return sendJson(res, 403, { error: 'Requisição não autorizada.' });

  const body = readJsonBody(req);
  const accessToken = body?.access_token;
  const refreshToken = body?.refresh_token;
  const expiresIn = body?.expires_in;
  if (typeof accessToken !== 'string' || typeof refreshToken !== 'string') {
    clearSessionCookies(res);
    return sendJson(res, 400, { error: 'Sessão inválida.' });
  }

  try {
    const user = await getAuthUser(accessToken);
    if (!user || !isAuthorizedUser(user)) {
      clearSessionCookies(res);
      return sendJson(res, 403, { error: 'Esta conta não está habilitada para acessar os dados.' });
    }
    setSessionCookies(res, { accessToken, refreshToken, expiresIn });
    return sendJson(res, 200, { status: 'ok' });
  } catch {
    clearSessionCookies(res);
    return sendJson(res, 502, { error: 'Não foi possível concluir a autenticação.' });
  }
}

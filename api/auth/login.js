import {
  clearSessionCookies,
  getAuthUser,
  getSupabaseConfig,
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
  const email = typeof body?.email === 'string' ? body.email.trim() : '';
  const password = typeof body?.password === 'string' ? body.password : '';
  if (!email || email.length > 254 || !password || password.length > 1024) {
    return sendJson(res, 400, { error: 'Informe um e-mail e uma senha válidos.' });
  }

  try {
    const { url, key } = getSupabaseConfig();
    const response = await fetch(`${url}/auth/v1/token?grant_type=password`, {
      method: 'POST',
      headers: { apikey: key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(7000),
      redirect: 'error',
    });
    if (!response.ok) return sendJson(res, 401, { error: 'Não foi possível entrar. Confira suas credenciais.' });

    const session = await response.json();
    const user = session.user || await getAuthUser(session.access_token);
    if (!session.access_token || !session.refresh_token || !isAuthorizedUser(user)) {
      clearSessionCookies(res);
      return sendJson(res, 403, { error: 'Esta conta não está habilitada para acessar os dados.' });
    }

    setSessionCookies(res, session);
    return sendJson(res, 200, { status: 'ok' });
  } catch {
    return sendJson(res, 502, { error: 'Não foi possível concluir a autenticação.' });
  }
}

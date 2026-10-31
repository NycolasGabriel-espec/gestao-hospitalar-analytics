import {
  getSupabaseConfig,
  isSameOriginRequest,
  readJsonBody,
  requireAuth,
  requirePost,
  sendJson,
} from '../../lib/api/supabase.js';

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

  try {
    const { url, key } = getSupabaseConfig();
    const response = await fetch(`${url}/auth/v1/user`, {
      method: 'PUT',
      headers: {
        apikey: key,
        Authorization: `Bearer ${session.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ password }),
      signal: AbortSignal.timeout(7000),
      redirect: 'error',
    });
    if (!response.ok) {
      return sendJson(res, 400, { error: 'Não foi possível atualizar a senha. Solicite um novo link de recuperação.' });
    }
    return sendJson(res, 200, { status: 'ok' });
  } catch {
    return sendJson(res, 502, { error: 'Não foi possível atualizar a senha agora.' });
  }
}

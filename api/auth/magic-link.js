import {
  getSupabaseConfig,
  isSameOriginRequest,
  readJsonBody,
  requirePost,
  sendJson,
} from '../../lib/api/supabase.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!requirePost(req, res)) return;
  if (!isSameOriginRequest(req)) return sendJson(res, 403, { error: 'Requisição não autorizada.' });

  const body = readJsonBody(req);
  const email = typeof body?.email === 'string' ? body.email.trim() : '';
  if (!email || email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return sendJson(res, 400, { error: 'Informe um e-mail válido.' });
  }

  try {
    const { url, key } = getSupabaseConfig();
    const origin = new URL(req.headers.origin).origin;
    const redirectTo = new URL('/login.html', origin);
    const endpoint = new URL('/auth/v1/otp', url);
    endpoint.searchParams.set('redirect_to', redirectTo.toString());
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { apikey: key, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, create_user: false }),
      signal: AbortSignal.timeout(7000),
      redirect: 'error',
    });

    if (!response.ok) {
      const message = response.status === 429
        ? 'Muitos e-mails foram solicitados. Aguarde e tente novamente.'
        : 'Não foi possível enviar o link agora. Tente novamente mais tarde.';
      return sendJson(res, response.status === 429 ? 429 : 503, { error: message });
    }

    return sendJson(res, 200, { status: 'sent' });
  } catch {
    return sendJson(res, 503, { error: 'Não foi possível enviar o link agora. Tente novamente mais tarde.' });
  }
}

import {
  getSessionTokens,
  getSupabaseConfig,
  isSameOriginRequest,
  requirePost,
  clearSessionCookies,
  sendJson,
} from '../../lib/api/supabase.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!requirePost(req, res)) return;
  if (!isSameOriginRequest(req)) return sendJson(res, 403, { error: 'Requisição não autorizada.' });

  const { accessToken } = getSessionTokens(req);
  try {
    if (accessToken) {
      const { url, key } = getSupabaseConfig();
      await fetch(`${url}/auth/v1/logout`, {
        method: 'POST',
        headers: { apikey: key, Authorization: `Bearer ${accessToken}` },
        signal: AbortSignal.timeout(5000),
        redirect: 'error',
      });
    }
  } catch {
    // Clearing browser cookies is still necessary if the upstream sign-out is unavailable.
  }
  clearSessionCookies(res);
  return sendJson(res, 200, { status: 'ok' });
}

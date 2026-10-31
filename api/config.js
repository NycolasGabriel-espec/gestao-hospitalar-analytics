import { getSupabaseConfig, handleError, requireGet, sendJson } from '../lib/api/supabase.js';

export default function handler(req, res) {
  if (!requireGet(req, res)) return;
  try {
    const { url, key } = getSupabaseConfig();
    sendJson(res, 200, { url, publishableKey: key });
  } catch (error) {
    handleError(res, error);
  }
}

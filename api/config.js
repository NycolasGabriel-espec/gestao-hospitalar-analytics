import { requireGet, sendJson } from '../lib/api/supabase.js';

export default function handler(req, res) {
  if (!requireGet(req, res)) return;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_KEY;
  if (!url || !key) {
    return sendJson(res, 503, { error: 'Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY na Vercel.' });
  }
  sendJson(res, 200, { url: url.replace(/\/$/, ''), publishableKey: key }, { 'Cache-Control': 'no-store' });
}

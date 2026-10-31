import { requireGet, sendJson } from '../lib/api/supabase.js';

export default function handler(req, res) {
  if (!requireGet(req, res)) return;
  sendJson(res, 200, { status: 'ok', service: 'gestao-hospitalar-analytics-api' });
}

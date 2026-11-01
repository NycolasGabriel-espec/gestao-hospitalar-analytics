import { checkDatabase, requireGet, sendJson } from '../lib/api/mysql.js';

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  try {
    await checkDatabase();
    sendJson(res, 200, { status: 'ok', service: 'gestao-hospitalar-analytics-api' });
  } catch {
    sendJson(res, 503, { status: 'unavailable', service: 'gestao-hospitalar-analytics-api' });
  }
}

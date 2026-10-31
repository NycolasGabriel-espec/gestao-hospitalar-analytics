import { handleError, parseLimit, queryView, requireAuth, requireGet, sendJson } from '../lib/api/supabase.js';

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  const auth = await requireAuth(req, res);
  if (!auth) return;
  const limit = parseLimit(req.query.limit);
  if (!limit) return sendJson(res, 400, { error: 'limit deve ser um inteiro entre 1 e 1000.' });
  const filters = {};
  for (const key of ['ano_mes', 'id_leito']) {
    if (req.query[key]) filters[key] = String(req.query[key]).slice(0, 40);
  }
  try {
    const data = await queryView('vw_eficiencia_leitos_setor', {
      select: 'ano_mes,id_leito,tipo_acomodacao,setor_hospitalar,leitos_operacionais,total_admissoes,dias_permanencia_coorte,dias_uti_reportados_coorte,leitos_dia_teoricos,taxa_ocupacao_pct,admissoes_por_leito_aproximado',
      filters, limit, accessToken: auth.accessToken,
    });
    sendJson(res, 200, { data, count: data.length, limit });
  } catch (error) { handleError(res, error); }
}

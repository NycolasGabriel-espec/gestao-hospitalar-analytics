import { handleError, parseLimit, queryView, requireAuth, requireGet, sendJson } from '../lib/api/supabase.js';

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  const auth = await requireAuth(req, res);
  if (!auth) return;
  const limit = parseLimit(req.query.limit);
  if (!limit) return sendJson(res, 400, { error: 'limit deve ser um inteiro entre 1 e 1000.' });
  const filters = {};
  for (const key of ['ano_mes', 'cid_10', 'especialidade', 'grau_severidade']) {
    if (req.query[key]) filters[key] = String(req.query[key]).slice(0, 80);
  }
  try {
    const data = await queryView('vw_detalhe_clinico_risco', {
      select: 'ano_mes,cid_10,descricao_cid,grau_severidade,especialidade,descricao_procedimento,faixa_etaria,volume_internacoes,tmp_medio,custo_medio,taxa_mortalidade_pct,taxa_readmissao_pct',
      filters, limit, accessToken: auth.accessToken,
    });
    sendJson(res, 200, { data, count: data.length, limit });
  } catch (error) { handleError(res, error); }
}

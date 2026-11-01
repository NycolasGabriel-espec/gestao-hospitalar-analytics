import { handleError, parseLimit, queryView, requireAuth, requireGet, sendJson } from '../lib/api/mysql.js';

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  const auth = await requireAuth(req, res);
  if (!auth) return;
  const limit = parseLimit(req.query.limit);
  if (!limit) return sendJson(res, 400, { error: 'limit deve ser um inteiro entre 1 e 1000.' });
  const filters = {};
  for (const key of ['ano_mes', 'especialidade']) {
    if (req.query[key]) filters[key] = String(req.query[key]).slice(0, 80);
  }
  try {
    const data = await queryView('vw_painel_executivo_mensal', {
      select: 'ano_mes,ano,mes,nome_mes,especialidade,volume_internacoes,receita_total,custo_total,custo_opme,margem_contribuicao,margem_pct,tmp_medio,taxa_readmissao_pct,taxa_mortalidade_pct',
      filters, limit,
    });
    sendJson(res, 200, { data, count: data.length, limit });
  } catch (error) { handleError(res, error); }
}

import { handleError, parseLimit, queryView, requireAuth, requireGet, sendJson } from '../lib/api/supabase.js';

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  const auth = await requireAuth(req, res);
  if (!auth) return;
  const limit = parseLimit(req.query.limit);
  if (!limit) return sendJson(res, 400, { error: 'limit deve ser um inteiro entre 1 e 1000.' });
  const filters = {};
  for (const key of ['cid_10', 'especialidade', 'grau_severidade']) {
    if (req.query[key]) filters[key] = String(req.query[key]).slice(0, 80);
  }
  try {
    // Não retorna identificadores de paciente nem de atendimento nesta API.
    const data = await queryView('vw_detalhe_clinico_risco', {
      select: 'sexo,idade,faixa_etaria,cid_10,descricao_cid,capitulo_cid,grau_severidade,especialidade,descricao_procedimento,tmp_protocolo_previsto,dias_permanencia,desvio_permanencia_dias,dias_uti,custo_total,custo_opme,receita_faturada,margem_contribuicao,status_desfecho,indicador_obito,readmissao_30d',
      filters, limit, accessToken: auth.accessToken,
    });
    sendJson(res, 200, { data, count: data.length, limit });
  } catch (error) { handleError(res, error); }
}

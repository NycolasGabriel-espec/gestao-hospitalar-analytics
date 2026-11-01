import { handleError, parseLimit, queryView, requireAuth, requireGet, sendJson } from '../lib/api/mysql.js';

const DIMENSIONS = {
  procedures: ['vw_dim_procedimento', 'id_procedimento,descricao_procedimento,especialidade,complexidade,tmp_protocolo_previsto'],
  diagnoses: ['vw_dim_diagnostico', 'cid_10,descricao_cid,capitulo_cid,grau_severidade'],
  beds: ['vw_dim_setor_leito', 'id_leito,tipo_acomodacao,setor_hospitalar,leitos_operacionais'],
  months: ['vw_dim_tempo', 'ano_mes,ano,mes,nome_mes'],
};

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  const auth = await requireAuth(req, res);
  if (!auth) return;
  const dimension = String(req.query.dimension || '');
  const config = DIMENSIONS[dimension];
  if (!config) return sendJson(res, 400, { error: 'dimension deve ser procedures, diagnoses, beds ou months.' });
  const limit = parseLimit(req.query.limit, 1000);
  if (!limit) return sendJson(res, 400, { error: 'limit deve ser um inteiro entre 1 e 1000.' });
  try {
    const data = await queryView(config[0], { select: config[1], limit });
    sendJson(res, 200, { data, count: data.length, limit });
  } catch (error) { handleError(res, error); }
}

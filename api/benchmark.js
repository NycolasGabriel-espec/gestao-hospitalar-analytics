import { handleError, queryView, requireAuth, requireGet, sendJson } from '../lib/api/mysql.js';
import publicSih from './public_sus_2025_sih_aggregates.js';

const LIMIT = 1000;

export default async function handler(req, res) {
  if (!requireGet(req, res)) return;
  const auth = await requireAuth(req, res);
  if (!auth) return;

  try {
    const period = req.query?.period || 'all';
    if (period !== 'all' && !/^2025-(0[1-9]|1[0-2])$/.test(String(period))) {
      return sendJson(res, 400, { error: 'Mês de admissão inválido.' });
    }
    const results = await Promise.allSettled([
      queryView('vw_public_sus_sih_mensal', {
        select: 'ano_mes,volume_aih,dias_permanencia,permanencia_media_dias,valor_aih_total,aihs_com_valor',
        limit: LIMIT,
      }),
      queryView(period === 'all' ? 'vw_public_sus_sih_procedimento_anual' : 'vw_public_sus_sih_procedimento_mensal', {
        select: 'ano_mes,id_procedimento,volume_aih,permanencia_media_dias,valor_aih_total,aihs_com_valor',
        ...(period !== 'all' ? { filters: { ano_mes: period } } : {}),
        limit: LIMIT,
      }),
      queryView('vw_public_cnes_leitos_mensal', {
        select: 'ano_mes,uf,estabelecimentos_hospitalares,leitos_gerais_sus,leitos_uti_sus,total_leitos_sus',
        limit: LIMIT,
      }),
      queryView('vw_public_sih_ocupacao_estimada_mensal', {
        select: 'ano_mes,dias_paciente_sih,leitos_sus_cnes,leitos_dia_disponiveis,ocupacao_estimada_pct',
        limit: LIMIT,
      }),
      queryView('vw_public_sisreg_fila_procedimento', {
        select: 'data_extracao,procedimento,solicitacoes_pendentes,espera_media_dias,espera_mediana_dias,espera_p90_dias,espera_max_dias',
        limit: LIMIT,
      }),
      queryView('vw_public_sus_dataset_manifest', {
        select: 'source_key,source_label,data_through,coverage_start,coverage_end,source_record_count,aggregate_row_count,loaded_at_utc',
        limit: 10,
      }),
    ]);
    const rowsOrEmpty = (result) => result.status === 'fulfilled' ? result.value : [];
    const databaseSummary = rowsOrEmpty(results[0]);
    const databaseProcedures = rowsOrEmpty(results[1]);
    const summary = databaseSummary.length ? databaseSummary : publicSih.summary;
    const procedures = databaseProcedures.length
      ? databaseProcedures
      : period === 'all'
        ? publicSih.procedures.filter((row) => row.ano_mes === '2025')
        : publicSih.procedures.filter((row) => row.ano_mes === period);
    const capacity = rowsOrEmpty(results[2]);
    const occupancy = rowsOrEmpty(results[3]);
    const waiting = rowsOrEmpty(results[4]);
    const datasetManifest = rowsOrEmpty(results[5]);
    const sihFallback = !databaseSummary.length || !databaseProcedures.length;
    const manifestSources = new Set(datasetManifest.map((item) => item.source_key));
    const requiredManifestSources = ['sih_sus', 'cnes', 'sisreg'];
    const missingManifestSources = requiredManifestSources.some((source) => !manifestSources.has(source));
    const manifestUnavailable = results[5].status === 'rejected' || missingManifestSources;
    const complementaryDataIncomplete = [2, 3, 4].some((index) =>
      results[index].status === 'rejected' || !results[index].value.length);
    sendJson(res, 200, {
      data: {
        summary, procedures, capacity, occupancy, waiting,
        meta: {
          sihFallback,
          complementaryDataIncomplete: complementaryDataIncomplete || manifestUnavailable,
          datasetManifest,
          manifestUnavailable,
        },
      },
      count: { summary: summary.length, procedures: procedures.length, capacity: capacity.length, occupancy: occupancy.length, waiting: waiting.length },
    });
  } catch (error) { handleError(res, error); }
}

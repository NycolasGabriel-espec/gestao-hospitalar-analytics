-- Expõe o ano de admissão no detalhe de risco para manter o panorama restrito a 2025.
-- Não altera linhas do SIH/SUS nem tabelas do esquema dimensional.

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_detalhe_clinico_risco AS
SELECT
    t.ano, t.ano_mes, d.cid_10, d.descricao_cid, d.grau_severidade,
    p.especialidade, p.descricao_procedimento, pac.faixa_etaria,
    COUNT(f.id_atendimento) AS volume_internacoes,
    CASE WHEN COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(AVG(f.dias_permanencia), 1) END AS tmp_medio,
    CASE WHEN COUNT(f.custo_total) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(AVG(f.custo_total), 2) END AS custo_medio,
    ROUND(SUM(CASE WHEN f.indicador_obito = 1 THEN 1 ELSE 0 END) * 100.0 /
          NULLIF(COUNT(f.indicador_obito), 0), 2) AS taxa_mortalidade_pct,
    ROUND(SUM(CASE WHEN f.readmissao_30d = 1 THEN 1 ELSE 0 END) * 100.0 /
          NULLIF(COUNT(f.readmissao_30d), 0), 2) AS taxa_readmissao_pct
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_paciente pac ON f.id_paciente = pac.id_paciente
JOIN dim_diagnostico d ON f.cid_10 = d.cid_10
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
GROUP BY t.ano, t.ano_mes, d.cid_10, d.descricao_cid, d.grau_severidade,
         p.especialidade, p.descricao_procedimento, pac.faixa_etaria
HAVING COUNT(f.id_atendimento) >= 10;

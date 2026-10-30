-- ==============================================================================
-- PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
-- ARQUIVO: 03_views_bi.sql
-- DESCRIÇÃO: Views Analíticas prontas para conexão com Power BI, Tableau ou Looker
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- VIEW 1: vw_painel_executivo_mensal
-- Alimenta os cartões de KPIs e gráficos de tendência da Tela Executiva
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_painel_executivo_mensal AS
SELECT
    t.ano_mes,
    t.ano,
    t.mes,
    t.nome_mes,
    p.especialidade,
    COUNT(f.id_atendimento) AS volume_internacoes,
    ROUND(SUM(f.receita_faturada), 2) AS receita_total,
    ROUND(SUM(f.custo_total), 2) AS custo_total,
    ROUND(SUM(f.custo_opme), 2) AS custo_opme,
    ROUND(SUM(f.margem_contribuicao), 2) AS margem_contribuicao,
    ROUND((SUM(f.margem_contribuicao) / NULLIF(SUM(f.receita_faturada), 0)) * 100.0, 2) AS margem_pct,
    ROUND(AVG(f.dias_permanencia), 1) AS tmp_medio,
    ROUND(SUM(CASE WHEN f.readmissao_30d THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(f.id_atendimento), 0), 2) AS taxa_readmissao_pct,
    ROUND(SUM(f.indicador_obito) * 100.0 / NULLIF(COUNT(f.id_atendimento), 0), 2) AS taxa_mortalidade_pct
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
GROUP BY t.ano_mes, t.ano, t.mes, t.nome_mes, p.especialidade;


-- ------------------------------------------------------------------------------
-- VIEW 2: vw_eficiencia_leitos_setor
-- Alimenta o Mapa de Calor e a Tela Operacional de Leitos
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_eficiencia_leitos_setor AS
SELECT
    t.ano_mes,
    l.id_leito,
    l.tipo_acomodacao,
    l.setor_hospitalar,
    l.leitos_operacionais,
    COUNT(f.id_atendimento) AS total_admissoes,
    SUM(f.dias_permanencia) AS dias_paciente_ocupados,
    SUM(f.dias_uti) AS dias_uti_ocupados,
    (l.leitos_operacionais * 30) AS leitos_dia_base_30d,
    ROUND((SUM(f.dias_permanencia) * 100.0) / NULLIF(l.leitos_operacionais * 30, 0), 2) AS taxa_ocupacao_pct,
    ROUND(COUNT(f.id_atendimento) * 1.0 / NULLIF(l.leitos_operacionais, 0), 2) AS giro_leito
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_setor_leito l ON f.id_leito = l.id_leito
GROUP BY t.ano_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais;


-- ------------------------------------------------------------------------------
-- VIEW 3: vw_detalhe_clinico_risco
-- Alimenta a Tela de Detalhamento de Risco e Readmissão (Filtros por CID e Paciente)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_detalhe_clinico_risco AS
SELECT
    f.id_atendimento,
    f.id_paciente,
    pac.sexo,
    pac.idade,
    pac.faixa_etaria,
    d.cid_10,
    d.descricao_cid,
    d.capitulo_cid,
    d.grau_severidade,
    p.especialidade,
    p.descricao_procedimento,
    p.tmp_protocolo_previsto,
    f.dias_permanencia,
    (f.dias_permanencia - p.tmp_protocolo_previsto) AS desvio_permanencia_dias,
    f.dias_uti,
    f.custo_total,
    f.custo_opme,
    f.receita_faturada,
    f.margem_contribuicao,
    f.status_desfecho,
    f.indicador_obito,
    f.readmissao_30d
FROM fato_internacoes f
JOIN dim_paciente pac ON f.id_paciente = pac.id_paciente
JOIN dim_diagnostico d ON f.cid_10 = d.cid_10
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento;

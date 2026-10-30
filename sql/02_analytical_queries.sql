-- ==============================================================================
-- PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
-- ARQUIVO: 02_analytical_queries.sql
-- DESCRIÇÃO: Consultas SQL Analíticas Avançadas para Responder às Dores de Negócio
-- DIALETO: ANSI SQL (PostgreSQL, DuckDB, BigQuery, MySQL 8.0+)
-- ==============================================================================

-- ==============================================================================
-- PERGUNTA 1: RENTABILIDADE E CUSTOS POR ESPECIALIDADE E PROCEDIMENTO
-- Objetivo: Identificar especialidades deficitárias, o peso de OPME na margem
--           e procedimentos que geram prejuízo operacional crônico.
-- ==============================================================================
WITH analise_rentabilidade AS (
    SELECT
        p.especialidade,
        p.id_procedimento,
        p.descricao_procedimento,
        COUNT(f.id_atendimento) AS total_internacoes,
        ROUND(SUM(f.receita_faturada), 2) AS receita_total,
        ROUND(SUM(f.custo_total), 2) AS custo_total,
        ROUND(SUM(f.custo_opme), 2) AS custo_total_opme,
        ROUND(SUM(f.margem_contribuicao), 2) AS margem_contribuicao_total,
        ROUND(AVG(f.margem_contribuicao), 2) AS margem_media_por_paciente,
        ROUND((SUM(f.margem_contribuicao) / NULLIF(SUM(f.receita_faturada), 0)) * 100.0, 2) AS margem_percentual,
        ROUND((SUM(f.custo_opme) / NULLIF(SUM(f.custo_total), 0)) * 100.0, 2) AS percentual_peso_opme
    FROM fato_internacoes f
    JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
    GROUP BY p.especialidade, p.id_procedimento, p.descricao_procedimento
)
SELECT
    especialidade,
    id_procedimento,
    descricao_procedimento,
    total_internacoes,
    receita_total,
    custo_total,
    custo_total_opme,
    percentual_peso_opme,
    margem_contribuicao_total,
    margem_media_por_paciente,
    margem_percentual,
    CASE 
        WHEN margem_percentual < 0 THEN '🔴 Prejuízo Crítico'
        WHEN margem_percentual BETWEEN 0 AND 10 THEN '🟡 Margem Estreita'
        ELSE '🟢 Alta Rentabilidade'
    END AS classificacao_economica
FROM analise_rentabilidade
WHERE total_internacoes >= 10
ORDER BY margem_contribuicao_total ASC;


-- ==============================================================================
-- PERGUNTA 2: DESVIO DE TEMPO MÉDIO DE PERMANÊNCIA (ALOS / TMP) VS. PROTOCOLO
-- Objetivo: Calcular a eficiência de permanência clínica e o custo financeiro
--           das diárias excedentes (além da diretriz clínica prevista).
-- ==============================================================================
WITH eficiencia_permanencia AS (
    SELECT
        d.capitulo_cid,
        d.cid_10,
        d.descricao_cid,
        p.tmp_protocolo_previsto,
        COUNT(f.id_atendimento) AS total_pacientes,
        ROUND(AVG(f.dias_permanencia), 2) AS tmp_real_medio,
        ROUND(AVG(f.dias_permanencia) - p.tmp_protocolo_previsto, 2) AS desvio_dias_protocolo,
        ROUND(AVG(f.custo_total / NULLIF(f.dias_permanencia, 0)), 2) AS custo_medio_diaria,
        -- Custo estimado de diárias além do protocolo clínico:
        ROUND(SUM(
            CASE 
                WHEN f.dias_permanencia > p.tmp_protocolo_previsto 
                THEN (f.dias_permanencia - p.tmp_protocolo_previsto) * (f.custo_total / NULLIF(f.dias_permanencia, 0))
                ELSE 0.00 
            END
        ), 2) AS custo_desperdicio_diarias_excedentes
    FROM fato_internacoes f
    JOIN dim_diagnostico d ON f.cid_10 = d.cid_10
    JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
    GROUP BY d.capitulo_cid, d.cid_10, d.descricao_cid, p.tmp_protocolo_previsto
)
SELECT
    capitulo_cid,
    cid_10,
    descricao_cid,
    total_pacientes,
    tmp_protocolo_previsto AS tmp_esperado,
    tmp_real_medio,
    desvio_dias_protocolo,
    custo_medio_diaria,
    custo_desperdicio_diarias_excedentes,
    CASE 
        WHEN desvio_dias_protocolo > 2.0 THEN '⚠️ Alta Ineficiência / Risco IRAS'
        WHEN desvio_dias_protocolo > 0.0 THEN '⚡ Desvio Moderado'
        ELSE '✅ Dentro da Meta'
    END AS status_aderencia_clinica
FROM eficiencia_permanencia
WHERE total_pacientes >= 15
ORDER BY custo_desperdicio_diarias_excedentes DESC;


-- ==============================================================================
-- PERGUNTA 3: GESTÃO DA TAXA DE OCUPAÇÃO DE LEITOS (BED OCCUPANCY RATE)
-- Objetivo: Medir a ocupação por setor ao longo do tempo (dias-paciente vs. leitos-dia),
--           sinalizando risco de colapso de UTI (>85%) ou ociosidade em enfermarias (<65%).
-- ==============================================================================
WITH capacidade_mes AS (
    SELECT
        t.ano_mes,
        t.ano,
        t.nome_mes,
        l.id_leito,
        l.tipo_acomodacao,
        l.setor_hospitalar,
        l.leitos_operacionais,
        COUNT(DISTINCT t.dia) AS dias_no_mes,
        -- Total de leitos-dia ofertados pela capacidade física:
        (l.leitos_operacionais * COUNT(DISTINCT t.dia)) AS total_leitos_dia_disponiveis
    FROM dim_tempo t
    CROSS JOIN dim_setor_leito l
    GROUP BY t.ano_mes, t.ano, t.nome_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais
),
demanda_paciente_mes AS (
    SELECT
        t.ano_mes,
        f.id_leito,
        COUNT(f.id_atendimento) AS total_admissoes,
        SUM(f.dias_permanencia) AS total_dias_paciente_ocupados,
        SUM(f.dias_uti) AS total_dias_uti_ocupados
    FROM fato_internacoes f
    JOIN dim_tempo t ON f.id_data_admissao = t.id_data
    GROUP BY t.ano_mes, f.id_leito
)
SELECT
    c.ano_mes,
    c.tipo_acomodacao,
    c.setor_hospitalar,
    c.leitos_operacionais,
    COALESCE(d.total_admissoes, 0) AS total_admissoes,
    COALESCE(d.total_dias_paciente_ocupados, 0) AS dias_paciente_ocupados,
    c.total_leitos_dia_disponiveis,
    ROUND(
        (COALESCE(d.total_dias_paciente_ocupados, 0) * 100.0) / NULLIF(c.total_leitos_dia_disponiveis, 0), 2
    ) AS taxa_ocupacao_percentual,
    ROUND(
        COALESCE(d.total_admissoes, 0) * 1.0 / NULLIF(c.leitos_operacionais, 0), 2
    ) AS giro_de_leito,
    CASE 
        WHEN (COALESCE(d.total_dias_paciente_ocupados, 0) * 100.0) / NULLIF(c.total_leitos_dia_disponiveis, 0) > 85.0 
            THEN '🚨 Risco Crítico de Saturação / Gargalo'
        WHEN (COALESCE(d.total_dias_paciente_ocupados, 0) * 100.0) / NULLIF(c.total_leitos_dia_disponiveis, 0) < 65.0 
            THEN '💤 Ociosidade Excessiva de Leitos'
        ELSE '🟢 Faixa Operacional Ótima (65% - 85%)'
    END AS status_capacidade
FROM capacidade_mes c
LEFT JOIN demanda_paciente_mes d 
    ON c.ano_mes = d.ano_mes AND c.id_leito = d.id_leito
ORDER BY c.ano_mes DESC, taxa_ocupacao_percentual DESC;


-- ==============================================================================
-- PERGUNTA 4: TAXA DE READMISSÃO EM 30 DIAS E QUALIDADE ASSISTENCIAL
-- Objetivo: Identificar diagnósticos e especialidades com alto índice de retorno
--           precoce ao hospital, associados ao desfecho e tempo de internação inicial.
-- ==============================================================================
SELECT
    p.especialidade,
    d.capitulo_cid,
    d.cid_10,
    d.descricao_cid,
    COUNT(f.id_atendimento) AS volume_internacoes,
    SUM(CASE WHEN f.readmissao_30d THEN 1 ELSE 0 END) AS total_readmissoes,
    ROUND(
        SUM(CASE WHEN f.readmissao_30d THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(f.id_atendimento), 0), 2
    ) AS taxa_readmissao_30d_pct,
    ROUND(
        SUM(f.indicador_obito) * 100.0 / NULLIF(COUNT(f.id_atendimento), 0), 2
    ) AS taxa_mortalidade_pct,
    ROUND(AVG(f.dias_permanencia), 1) AS tmp_medio_dias,
    ROUND(SUM(CASE WHEN f.readmissao_30d THEN f.custo_total ELSE 0 END), 2) AS custo_total_reinternacoes
FROM fato_internacoes f
JOIN dim_diagnostico d ON f.cid_10 = d.cid_10
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
GROUP BY p.especialidade, d.capitulo_cid, d.cid_10, d.descricao_cid
HAVING COUNT(f.id_atendimento) >= 20
ORDER BY taxa_readmissao_30d_pct DESC;


-- ==============================================================================
-- CONSULTA BÔNUS: CURVA ABC DE GASTOS HOSPITALARES (PARETO 80/20)
-- Objetivo: Aplicar Window Functions analíticas para priorizar os 20% de
--           procedimentos que concentram 80% dos custos da instituição.
-- ==============================================================================
WITH custos_acumulados AS (
    SELECT
        p.id_procedimento,
        p.descricao_procedimento,
        p.especialidade,
        COUNT(f.id_atendimento) AS qtd_procedimentos,
        SUM(f.custo_total) AS custo_procedimento,
        SUM(SUM(f.custo_total)) OVER () AS custo_hospitalar_global,
        SUM(SUM(f.custo_total)) OVER (
            ORDER BY SUM(f.custo_total) DESC 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS custo_acumulado
    FROM fato_internacoes f
    JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
    GROUP BY p.id_procedimento, p.descricao_procedimento, p.especialidade
)
SELECT
    id_procedimento,
    descricao_procedimento,
    especialidade,
    qtd_procedimentos,
    ROUND(custo_procedimento, 2) AS custo_total_procedimento,
    ROUND((custo_procedimento / custo_hospitalar_global) * 100.0, 2) AS perc_custo_individual,
    ROUND((custo_acumulado / custo_hospitalar_global) * 100.0, 2) AS perc_acumulado_pareto,
    CASE
        WHEN (custo_acumulado / custo_hospitalar_global) <= 0.80 THEN 'Classe A (80% dos Custos - Foco Imediato)'
        WHEN (custo_acumulado / custo_hospitalar_global) <= 0.95 THEN 'Classe B (15% dos Custos - Monitoramento)'
        ELSE 'Classe C (5% dos Custos - Baixo Impacto)'
    END AS classificacao_abc
FROM custos_acumulados
ORDER BY custo_procedimento DESC;

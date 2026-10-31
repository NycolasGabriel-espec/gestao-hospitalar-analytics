-- ==============================================================================
-- PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
-- ARQUIVO: 02_analytical_queries.sql
-- DESCRIÇÃO: Consultas SQL Analíticas Avançadas para Responder às Dores de Negócio
-- DIALETO: PostgreSQL / DuckDB (uses FILTER and window functions)
-- Estas consultas são modelos. Valores clínicos ou financeiros desconhecidos
-- devem continuar NULL; limiares não substituem validação especializada.
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
        COUNT(f.receita_faturada) AS internacoes_com_valor_aiH,
        COUNT(f.custo_total) AS internacoes_com_custo,
        COUNT(f.margem_contribuicao) AS internacoes_com_margem,
        CASE WHEN COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND(SUM(f.receita_faturada), 2) END AS receita_total,
        CASE WHEN COUNT(f.custo_total) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND(SUM(f.custo_total), 2) END AS custo_total,
        CASE WHEN COUNT(f.custo_opme) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND(SUM(f.custo_opme), 2) END AS custo_total_opme,
        CASE WHEN COUNT(f.margem_contribuicao) < COUNT(f.id_atendimento)
                   OR COUNT(f.custo_total) < COUNT(f.id_atendimento)
                   OR COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND(SUM(f.margem_contribuicao), 2) END AS margem_contribuicao_total,
        CASE WHEN COUNT(f.margem_contribuicao) < COUNT(f.id_atendimento)
                   OR COUNT(f.custo_total) < COUNT(f.id_atendimento)
                   OR COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND(AVG(f.margem_contribuicao), 2) END AS margem_media_por_paciente,
        CASE WHEN COUNT(f.margem_contribuicao) < COUNT(f.id_atendimento)
                   OR COUNT(f.custo_total) < COUNT(f.id_atendimento)
                   OR COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND((SUM(f.margem_contribuicao) / NULLIF(SUM(f.receita_faturada), 0)) * 100.0, 2)
        END AS margem_percentual,
        CASE WHEN COUNT(f.custo_opme) < COUNT(f.id_atendimento)
                   OR COUNT(f.custo_total) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND((SUM(f.custo_opme) / NULLIF(SUM(f.custo_total), 0)) * 100.0, 2)
        END AS percentual_peso_opme
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
        WHEN margem_percentual IS NULL OR custo_total IS NULL OR receita_total IS NULL
            THEN 'Dados financeiros não disponíveis'
        WHEN margem_percentual < 0 THEN '🔴 Prejuízo Crítico'
        WHEN margem_percentual BETWEEN 0 AND 10 THEN '🟡 Margem Estreita'
        ELSE '🟢 Alta Rentabilidade'
    END AS classificacao_economica
FROM analise_rentabilidade
WHERE total_internacoes >= 10
ORDER BY margem_contribuicao_total ASC NULLS LAST;


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
        COUNT(f.dias_permanencia) AS internacoes_com_permanencia,
        ROUND(AVG(f.dias_permanencia), 2) AS tmp_real_medio,
        ROUND(AVG(f.dias_permanencia) - p.tmp_protocolo_previsto, 2) AS desvio_dias_protocolo,
        CASE WHEN COUNT(f.custo_total) < COUNT(f.id_atendimento)
                   OR COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
             ELSE ROUND(AVG(f.custo_total / NULLIF(f.dias_permanencia, 0)), 2)
        END AS custo_medio_diaria,
        -- Só estima custos quando todos os registros do grupo têm custo e
        -- permanência conhecidos e há protocolo informado.
        CASE
            WHEN p.tmp_protocolo_previsto IS NULL
              OR COUNT(f.custo_total) < COUNT(f.id_atendimento)
              OR COUNT(f.dias_permanencia) < COUNT(f.id_atendimento)
                THEN NULL
            ELSE ROUND(SUM(
                CASE
                    WHEN f.dias_permanencia > p.tmp_protocolo_previsto
                    THEN (f.dias_permanencia - p.tmp_protocolo_previsto)
                         * (f.custo_total / NULLIF(f.dias_permanencia, 0))
                    ELSE 0.00
                END
            ), 2)
        END AS custo_desperdicio_diarias_excedentes
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
        WHEN internacoes_com_permanencia < total_pacientes
            THEN 'Permanência incompleta; comparação não classificada'
        WHEN desvio_dias_protocolo IS NULL OR tmp_protocolo_previsto IS NULL
            THEN 'Dados insuficientes para comparar'
        WHEN desvio_dias_protocolo > 2.0 THEN 'Desvio acima de 2 dias; revisar clinicamente'
        WHEN desvio_dias_protocolo > 0.0 THEN 'Desvio positivo; revisar clinicamente'
        ELSE 'Sem desvio positivo observado'
    END AS status_desvio_protocolo
FROM eficiencia_permanencia
WHERE total_pacientes >= 15
ORDER BY custo_desperdicio_diarias_excedentes DESC NULLS LAST;


-- ==============================================================================
-- PERGUNTA 3: CAPACIDADE E VOLUME DE ADMISSÕES POR SETOR
-- O esquema não contém censo diário nem histórico de capacidade por período.
-- Portanto, não calcula taxa de ocupação nem classifica saturação/ociosidade.
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
        COUNT(DISTINCT t.dia) AS dias_calendario_no_mes,
        (l.leitos_operacionais * COUNT(DISTINCT t.dia)) AS leitos_dia_teoricos
    FROM dim_tempo t
    CROSS JOIN dim_setor_leito l
    GROUP BY t.ano_mes, t.ano, t.nome_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais
),
demanda_paciente_mes AS (
    SELECT
        t.ano_mes,
        f.id_leito,
        COUNT(f.id_atendimento) AS total_admissoes,
        COUNT(f.dias_permanencia) AS admissoes_com_permanencia_conhecida,
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
    CASE WHEN d.total_admissoes IS NULL THEN 0 ELSE d.total_dias_paciente_ocupados END AS dias_permanencia_da_coorte,
    c.leitos_dia_teoricos,
    CAST(NULL AS NUMERIC(7, 2)) AS taxa_ocupacao_percentual,
    ROUND(
        COALESCE(d.total_admissoes, 0) * 1.0 / NULLIF(c.leitos_operacionais, 0), 2
    ) AS admissoes_por_leito_aproximado,
    CASE
        WHEN c.leitos_operacionais IS NULL THEN 'Dados de capacidade não disponíveis'
        ELSE 'Ocupação não calculada: requer censo diário e capacidade histórica'
    END AS status_capacidade
FROM capacidade_mes c
LEFT JOIN demanda_paciente_mes d 
    ON c.ano_mes = d.ano_mes AND c.id_leito = d.id_leito
ORDER BY c.ano_mes DESC, total_admissoes DESC;


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
    CASE WHEN COUNT(f.readmissao_30d) = 0 THEN NULL
         ELSE COUNT(*) FILTER (WHERE f.readmissao_30d IS TRUE)
    END AS total_readmissoes,
    ROUND(
        COUNT(*) FILTER (WHERE f.readmissao_30d IS TRUE) * 100.0 / NULLIF(COUNT(f.readmissao_30d), 0), 2
    ) AS taxa_readmissao_30d_pct,
    ROUND(
        SUM(f.indicador_obito) * 100.0 / NULLIF(COUNT(f.indicador_obito), 0), 2
    ) AS taxa_mortalidade_pct,
    ROUND(AVG(f.dias_permanencia), 1) AS tmp_medio_dias,
    CASE
        WHEN COUNT(f.readmissao_30d) < COUNT(f.id_atendimento) THEN NULL
        WHEN COUNT(*) FILTER (WHERE f.readmissao_30d IS TRUE) = 0 THEN 0.00
        WHEN COUNT(f.custo_total) FILTER (WHERE f.readmissao_30d IS TRUE)
             < COUNT(*) FILTER (WHERE f.readmissao_30d IS TRUE) THEN NULL
        ELSE ROUND(SUM(f.custo_total) FILTER (WHERE f.readmissao_30d IS TRUE), 2)
    END AS custo_total_reinternacoes
FROM fato_internacoes f
JOIN dim_diagnostico d ON f.cid_10 = d.cid_10
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
GROUP BY p.especialidade, d.capitulo_cid, d.cid_10, d.descricao_cid
HAVING COUNT(f.id_atendimento) >= 20
ORDER BY taxa_readmissao_30d_pct DESC NULLS LAST;


-- ==============================================================================
-- CONSULTA BÔNUS: CURVA ABC DE GASTOS HOSPITALARES (PARETO 80/20)
-- Objetivo: Aplicar Window Functions analíticas para priorizar os 20% de
--           procedimentos que concentram 80% dos custos da instituição.
-- ==============================================================================
WITH custo_por_procedimento AS (
    SELECT
        p.id_procedimento,
        p.descricao_procedimento,
        p.especialidade,
        COUNT(f.id_atendimento) AS qtd_procedimentos,
        COUNT(f.custo_total) AS internacoes_com_custo,
        CASE WHEN COUNT(f.custo_total) < COUNT(f.id_atendimento) THEN NULL
             ELSE SUM(f.custo_total) END AS custo_procedimento
    FROM fato_internacoes f
    JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
    GROUP BY p.id_procedimento, p.descricao_procedimento, p.especialidade
), custos_acumulados AS (
    SELECT
        id_procedimento,
        descricao_procedimento,
        especialidade,
        qtd_procedimentos,
        internacoes_com_custo,
        custo_procedimento,
        SUM(qtd_procedimentos) OVER () AS internacoes_total,
        SUM(internacoes_com_custo) OVER () AS internacoes_com_custo_total,
        SUM(custo_procedimento) OVER () AS custo_hospitalar_global,
        SUM(custo_procedimento) OVER (
            ORDER BY custo_procedimento DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS custo_acumulado
)
SELECT
    id_procedimento,
    descricao_procedimento,
    especialidade,
    qtd_procedimentos,
    ROUND(custo_procedimento, 2) AS custo_total_procedimento,
    CASE WHEN internacoes_com_custo_total < internacoes_total OR custo_hospitalar_global IS NULL THEN NULL
         ELSE ROUND((custo_procedimento / custo_hospitalar_global) * 100.0, 2)
    END AS perc_custo_individual,
    CASE WHEN internacoes_com_custo_total < internacoes_total OR custo_hospitalar_global IS NULL THEN NULL
         ELSE ROUND((custo_acumulado / custo_hospitalar_global) * 100.0, 2)
    END AS perc_acumulado_pareto,
    CASE
        WHEN internacoes_com_custo_total < internacoes_total
          OR custo_hospitalar_global IS NULL OR custo_acumulado IS NULL
            THEN 'Dados de custo não disponíveis'
        WHEN (custo_acumulado / custo_hospitalar_global) <= 0.80 THEN 'Classe A (80% dos Custos - Foco Imediato)'
        WHEN (custo_acumulado / custo_hospitalar_global) <= 0.95 THEN 'Classe B (15% dos Custos - Monitoramento)'
        ELSE 'Classe C (5% dos Custos - Baixo Impacto)'
    END AS classificacao_abc
FROM custos_acumulados
ORDER BY custo_procedimento DESC NULLS LAST;

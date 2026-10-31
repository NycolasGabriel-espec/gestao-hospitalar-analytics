-- ==============================================================================
-- PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
-- ARQUIVO: supabase_setup.sql
-- DESCRIÇÃO: Script completo de inicialização para o banco Supabase (PostgreSQL)
-- INCLUI: Star Schema DDL, Índices, Views Analíticas de BI, RLS e Permissões de API
-- ==============================================================================

-- Garantir que estamos no schema público
SET search_path TO public;
BEGIN;

-- ------------------------------------------------------------------------------
-- 1. CRIAÇÃO SEM APAGAR TABELAS OU DADOS EXISTENTES
-- ------------------------------------------------------------------------------

-- ------------------------------------------------------------------------------
-- 2. CRIAÇÃO DAS TABELAS DIMENSIONAIS
-- ------------------------------------------------------------------------------

-- Dimensão Tempo (Calendário analítico)
CREATE TABLE IF NOT EXISTS dim_tempo (
    id_data INTEGER PRIMARY KEY,           -- Chave YYYYMMDD (ex: 20230115)
    data_completa DATE NOT NULL,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    dia INTEGER NOT NULL,
    nome_mes VARCHAR(20) NOT NULL,
    trimestre INTEGER NOT NULL,
    ano_mes VARCHAR(7) NOT NULL,           -- ex: '2023-01'
    dia_semana VARCHAR(20) NOT NULL,
    eh_fim_semana BOOLEAN NOT NULL
);

COMMENT ON TABLE dim_tempo IS 'Dimensão de tempo detalhada por dia para análises temporais e sazonais';

-- Dimensão Paciente (Dados demográficos pseudonimizados)
CREATE TABLE IF NOT EXISTS dim_paciente (
    id_paciente VARCHAR(64) PRIMARY KEY,   -- Identificador HMAC pseudonimizado
    sexo VARCHAR(1) NOT NULL,              -- 'M' ou 'F'
    faixa_etaria VARCHAR(30) NOT NULL      -- Faixa etária; não armazena idade exata ou município
);

COMMENT ON TABLE dim_paciente IS 'Dimensão pseudonimizada com sexo e faixa etária, sem idade exata ou município';

-- Dimensão Procedimento (SIGTAP SUS / TUSS)
CREATE TABLE IF NOT EXISTS dim_procedimento (
    id_procedimento VARCHAR(12) PRIMARY KEY, -- Código SIGTAP (10 dígitos)
    descricao_procedimento VARCHAR(255) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,      -- 'Ortopedia', 'Cardiologia', etc.
    complexidade VARCHAR(30) NOT NULL,       -- 'Média Complexidade', 'Alta Complexidade'
    porte_cirurgico VARCHAR(20),            -- 'Pequeno', 'Médio', 'Grande', 'Clínico'
    tmp_protocolo_previsto NUMERIC(4, 1) -- Preencher apenas com protocolo clínico validado
);

COMMENT ON TABLE dim_procedimento IS 'Catálogo de procedimentos; classificação heurística deve ser validada e TMP só deve vir de protocolo aprovado';

-- Dimensão Diagnóstico (CID-10)
CREATE TABLE IF NOT EXISTS dim_diagnostico (
    cid_10 VARCHAR(10) PRIMARY KEY,         -- Código CID-10 (ex: 'I21.9')
    descricao_cid VARCHAR(255) NOT NULL,
    capitulo_cid VARCHAR(120) NOT NULL,     -- Agrupamento amplo aproximado
    grau_severidade VARCHAR(30) NOT NULL    -- 'Não classificado' quando não houver classificação validada
);

COMMENT ON TABLE dim_diagnostico IS 'Códigos CID-10; capítulo pode ser aproximado e severidade não é inferida do código';

-- Dimensão Setor e Leito (Capacidade Instalada)
CREATE TABLE IF NOT EXISTS dim_setor_leito (
    id_leito VARCHAR(20) PRIMARY KEY,       -- Identificador da unidade
    tipo_acomodacao VARCHAR(50) NOT NULL,   -- 'UTI Adulto & Crítica', 'Enfermaria Cirúrgica', etc.
    setor_hospitalar VARCHAR(80) NOT NULL,  -- Bloco / Pavilhão
    leitos_operacionais INTEGER              -- NULL quando a fonte não informa capacidade
);

COMMENT ON TABLE dim_setor_leito IS 'Capacidade por setor quando informada; SIH/SUS pode usar a categoria Não informado na fonte';

-- ------------------------------------------------------------------------------
-- 3. CRIAÇÃO DA TABELA FATO: INTERNAÇÕES HOSPITALARES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fato_internacoes (
    id_atendimento VARCHAR(64) PRIMARY KEY, -- HMAC do número de atendimento de origem
    id_paciente VARCHAR(64) NOT NULL REFERENCES dim_paciente(id_paciente),
    id_procedimento VARCHAR(12) NOT NULL REFERENCES dim_procedimento(id_procedimento),
    cid_10 VARCHAR(10) NOT NULL REFERENCES dim_diagnostico(cid_10),
    id_leito VARCHAR(20) NOT NULL REFERENCES dim_setor_leito(id_leito),
    id_data_admissao INTEGER NOT NULL REFERENCES dim_tempo(id_data),
    id_data_alta INTEGER REFERENCES dim_tempo(id_data),
    
    -- Métricas de Permanência e Ocupação
    dias_permanencia INTEGER,                -- NULL quando ausente na fonte
    dias_uti INTEGER,                        -- NULL quando não informado na fonte
    qtd_diarias INTEGER,                     -- NULL quando não informado na fonte
    
    -- Métricas Financeiras e Custos (R$)
    custo_hospitalar NUMERIC(12, 2),              -- NULL: AIH não informa custo contábil do hospital
    custo_servicos_profissionais NUMERIC(12, 2),   -- NULL: valor da AIH não é custo interno
    custo_opme NUMERIC(12, 2),                    -- NULL quando não há custo validado
    custo_sadt NUMERIC(12, 2),                    -- NULL quando não há custo validado
    custo_total NUMERIC(12, 2),                   -- NULL sem dados de custo contábil
    receita_faturada NUMERIC(12, 2),              -- Valor da AIH; não prova recebimento
    margem_contribuicao NUMERIC(12, 2),            -- NULL sem valores contábeis validados
    
    -- Desfechos e Indicadores de Qualidade Clínica
    status_desfecho VARCHAR(80),                    -- NULL se a fonte não permite classificar
    indicador_obito INTEGER,                        -- NULL se não informado
    readmissao_30d BOOLEAN                       -- NULL quando a fonte não permite identificar a pessoa
);

-- Atualizações seguras para instalações anteriores. Removem apenas os campos
-- demográficos que não são necessários ao analytics e ampliam a chave HMAC.
DROP VIEW IF EXISTS vw_detalhe_clinico_risco;
DROP VIEW IF EXISTS vw_eficiencia_leitos_setor;
ALTER TABLE dim_paciente DROP COLUMN IF EXISTS idade;
ALTER TABLE dim_paciente DROP COLUMN IF EXISTS municipio_residencia;
ALTER TABLE dim_paciente DROP COLUMN IF EXISTS uf_residencia;
ALTER TABLE fato_internacoes ALTER COLUMN id_atendimento TYPE VARCHAR(64);
ALTER TABLE fato_internacoes ALTER COLUMN readmissao_30d DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN readmissao_30d DROP DEFAULT;
ALTER TABLE fato_internacoes ALTER COLUMN id_data_alta DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN dias_permanencia DROP NOT NULL;
ALTER TABLE dim_procedimento ALTER COLUMN tmp_protocolo_previsto DROP NOT NULL;
ALTER TABLE dim_setor_leito ALTER COLUMN leitos_operacionais DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN dias_uti DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN dias_uti DROP DEFAULT;
ALTER TABLE fato_internacoes ALTER COLUMN qtd_diarias DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN custo_hospitalar DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN custo_servicos_profissionais DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN custo_opme DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN custo_opme DROP DEFAULT;
ALTER TABLE fato_internacoes ALTER COLUMN custo_sadt DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN custo_sadt DROP DEFAULT;
ALTER TABLE fato_internacoes ALTER COLUMN custo_total DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN receita_faturada DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN margem_contribuicao DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN status_desfecho TYPE VARCHAR(80);
ALTER TABLE fato_internacoes ALTER COLUMN status_desfecho DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN indicador_obito DROP NOT NULL;
ALTER TABLE fato_internacoes ALTER COLUMN indicador_obito DROP DEFAULT;

COMMENT ON TABLE fato_internacoes IS 'Tabela fato granular; dados de saúde sensíveis, com custos e desfechos possivelmente desconhecidos';

-- ------------------------------------------------------------------------------
-- 4. ÍNDICES ANALÍTICOS (Otimização para consultas agregadas e filtros de BI)
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fato_data_admissao ON fato_internacoes(id_data_admissao);
CREATE INDEX IF NOT EXISTS idx_fato_data_leito ON fato_internacoes(id_data_admissao, id_leito);
CREATE INDEX IF NOT EXISTS idx_fato_data_procedimento ON fato_internacoes(id_data_admissao, id_procedimento);
CREATE INDEX IF NOT EXISTS idx_fato_data_alta ON fato_internacoes(id_data_alta);
CREATE INDEX IF NOT EXISTS idx_fato_paciente ON fato_internacoes(id_paciente);
CREATE INDEX IF NOT EXISTS idx_fato_procedimento ON fato_internacoes(id_procedimento);
CREATE INDEX IF NOT EXISTS idx_fato_diagnostico ON fato_internacoes(cid_10);
CREATE INDEX IF NOT EXISTS idx_fato_leito ON fato_internacoes(id_leito);
-- readmissao_30d and indicador_obito are low-cardinality metrics aggregated
-- over the fact table; standalone B-tree indexes do not help those scans.
-- margem_contribuicao is aggregated/sorted in reports, not used as a row filter.

-- ------------------------------------------------------------------------------
-- 5. VIEWS ANALÍTICAS PARA BI E DASHBOARDS
-- ------------------------------------------------------------------------------

-- Views padrão executam com privilégios do proprietário. A autorização usa as
-- claims definidas pelo PostgREST sem depender de permissões no schema auth;
-- a conexão PostgreSQL dedicada do Power BI é liberada pelo session_user.
-- View 1: Painel Executivo Mensal, ocultando grupos com menos de 10 internações.
CREATE OR REPLACE VIEW vw_painel_executivo_mensal WITH (security_barrier = true) AS
SELECT
    t.ano_mes, t.ano, t.mes, t.nome_mes, p.especialidade,
    COUNT(f.id_atendimento) AS volume_internacoes,
    CASE WHEN COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(SUM(f.receita_faturada), 2) END AS receita_total,
    CASE WHEN COUNT(f.custo_total) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(SUM(f.custo_total), 2) END AS custo_total,
    CASE WHEN COUNT(f.custo_opme) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(SUM(f.custo_opme), 2) END AS custo_opme,
    CASE WHEN COUNT(f.margem_contribuicao) < COUNT(f.id_atendimento)
                   OR COUNT(f.custo_total) < COUNT(f.id_atendimento)
                   OR COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(SUM(f.margem_contribuicao), 2) END AS margem_contribuicao,
    CASE WHEN COUNT(f.margem_contribuicao) < COUNT(f.id_atendimento)
                   OR COUNT(f.custo_total) < COUNT(f.id_atendimento)
                   OR COUNT(f.receita_faturada) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND((SUM(f.margem_contribuicao) / NULLIF(SUM(f.receita_faturada), 0)) * 100.0, 2)
    END AS margem_pct,
    CASE WHEN COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(AVG(f.dias_permanencia), 1) END AS tmp_medio,
    ROUND(COUNT(*) FILTER (WHERE f.readmissao_30d IS TRUE) * 100.0 / NULLIF(COUNT(f.readmissao_30d), 0), 2) AS taxa_readmissao_pct,
    ROUND(SUM(f.indicador_obito) * 100.0 / NULLIF(COUNT(f.indicador_obito), 0), 2) AS taxa_mortalidade_pct
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%'
GROUP BY t.ano_mes, t.ano, t.mes, t.nome_mes, p.especialidade
HAVING COUNT(f.id_atendimento) >= 10;

COMMENT ON VIEW vw_painel_executivo_mensal IS 'KPIs executivos agregados; exige conta aprovada e oculta grupos pequenos';

-- View 2: admissões por setor. Dias de permanência agrupados pela admissão
-- não equivalem a censo diário; ocupação fica NULL até existir fonte diária.
CREATE OR REPLACE VIEW vw_eficiencia_leitos_setor WITH (security_barrier = true) AS
SELECT
    t.ano_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais,
    COUNT(f.id_atendimento) AS total_admissoes,
    CASE WHEN COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
         ELSE SUM(f.dias_permanencia) END AS dias_permanencia_coorte,
    CASE WHEN COUNT(f.dias_uti) < COUNT(f.id_atendimento) THEN NULL
         ELSE SUM(f.dias_uti) END AS dias_uti_reportados_coorte,
    (l.leitos_operacionais * COUNT(DISTINCT t.dia)) AS leitos_dia_teoricos,
    CAST(NULL AS NUMERIC(7, 2)) AS taxa_ocupacao_pct,
    ROUND(COUNT(f.id_atendimento) * 1.0 / NULLIF(l.leitos_operacionais, 0), 2) AS admissoes_por_leito_aproximado
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_setor_leito l ON f.id_leito = l.id_leito
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%'
GROUP BY t.ano_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais
HAVING COUNT(f.id_atendimento) >= 10;

COMMENT ON VIEW vw_eficiencia_leitos_setor IS 'Admissões mensais por coorte; ocupação não calculada sem censo diário e capacidade histórica';

-- Publica coortes agregadas, sem identificadores individuais.
CREATE VIEW vw_detalhe_clinico_risco WITH (security_barrier = true) AS
SELECT
    t.ano_mes, d.cid_10, d.descricao_cid, d.grau_severidade,
    p.especialidade, p.descricao_procedimento, pac.faixa_etaria,
    COUNT(f.id_atendimento) AS volume_internacoes,
    CASE WHEN COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(AVG(f.dias_permanencia), 1) END AS tmp_medio,
    CASE WHEN COUNT(f.custo_total) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(AVG(f.custo_total), 2) END AS custo_medio,
    ROUND(COUNT(*) FILTER (WHERE f.indicador_obito = 1) * 100.0 / NULLIF(COUNT(f.indicador_obito), 0), 2) AS taxa_mortalidade_pct,
    ROUND(COUNT(*) FILTER (WHERE f.readmissao_30d IS TRUE) * 100.0 / NULLIF(COUNT(f.readmissao_30d), 0), 2) AS taxa_readmissao_pct
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_paciente pac ON f.id_paciente = pac.id_paciente
JOIN dim_diagnostico d ON f.cid_10 = d.cid_10
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%'
GROUP BY t.ano_mes, d.cid_10, d.descricao_cid, d.grau_severidade,
         p.especialidade, p.descricao_procedimento, pac.faixa_etaria
HAVING COUNT(f.id_atendimento) >= 10;

COMMENT ON VIEW vw_detalhe_clinico_risco IS 'Indicadores por coorte com supressão mínima de 10 internações; sem identificadores individuais';

-- Dimensões de referência: não expõem a dimensão demográfica nem a tabela fato.
CREATE OR REPLACE VIEW vw_dim_procedimento WITH (security_barrier = true) AS
SELECT id_procedimento, descricao_procedimento, especialidade, complexidade, tmp_protocolo_previsto
FROM dim_procedimento
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%';

CREATE OR REPLACE VIEW vw_dim_diagnostico WITH (security_barrier = true) AS
SELECT cid_10, descricao_cid, capitulo_cid, grau_severidade
FROM dim_diagnostico
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%';

CREATE OR REPLACE VIEW vw_dim_setor_leito WITH (security_barrier = true) AS
SELECT id_leito, tipo_acomodacao, setor_hospitalar, leitos_operacionais
FROM dim_setor_leito
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%';

CREATE OR REPLACE VIEW vw_dim_tempo WITH (security_barrier = true) AS
SELECT ano_mes, ano, mes, nome_mes
FROM dim_tempo
WHERE COALESCE((NULLIF(current_setting('request.jwt.claims', true), '')::jsonb -> 'app_metadata' ->> 'hospital_analytics_access') = 'true', false)
   OR NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role' = 'service_role'
   OR session_user = 'powerbi_reader' OR session_user LIKE 'powerbi_reader.%';

-- ------------------------------------------------------------------------------
-- 6. POLÍTICAS DE ROW LEVEL SECURITY (RLS) E ACESSO À API SUPABASE
-- ------------------------------------------------------------------------------
-- Habilitar RLS em todas as tabelas
ALTER TABLE dim_tempo ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_paciente ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_procedimento ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_diagnostico ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_setor_leito ENABLE ROW LEVEL SECURITY;
ALTER TABLE fato_internacoes ENABLE ROW LEVEL SECURITY;

-- Tabelas internas sem políticas: mesmo se SELECT for concedido por engano,
-- RLS nega todas as linhas. Remova políticas antigas com quaisquer nomes.
DO $$
DECLARE
    old_policy RECORD;
BEGIN
    FOR old_policy IN
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = ANY (ARRAY[
              'dim_tempo', 'dim_paciente', 'dim_procedimento',
              'dim_diagnostico', 'dim_setor_leito', 'fato_internacoes'
          ])
    LOOP
        EXECUTE format(
            'DROP POLICY %I ON %I.%I',
            old_policy.policyname, old_policy.schemaname, old_policy.tablename
        );
    END LOOP;
END $$;

-- Fechar somente os objetos deste projeto; preservar grants de outros objetos
-- que eventualmente compartilhem o schema public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
-- Bloqueia a exposição automática de futuras tabelas/sequências criadas por
-- postgres neste schema; novos objetos exigirão GRANT explícito e RLS revisada.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE dim_tempo, dim_paciente, dim_procedimento,
    dim_diagnostico, dim_setor_leito, fato_internacoes
    FROM PUBLIC, anon, authenticated;
-- Se o papel de BI já existir por uma instalação antiga, retire grants
-- diretos das tabelas granulares antes de manter a leitura somente pelas views.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'powerbi_reader') THEN
        EXECUTE 'REVOKE ALL ON TABLE dim_tempo, dim_paciente, dim_procedimento, '
             || 'dim_diagnostico, dim_setor_leito, fato_internacoes FROM powerbi_reader';
    END IF;
END $$;
REVOKE ALL ON TABLE vw_painel_executivo_mensal, vw_eficiencia_leitos_setor,
    vw_detalhe_clinico_risco, vw_dim_procedimento, vw_dim_diagnostico,
    vw_dim_setor_leito, vw_dim_tempo
    FROM PUBLIC, anon, authenticated;
GRANT SELECT ON vw_painel_executivo_mensal,
                vw_eficiencia_leitos_setor,
                vw_detalhe_clinico_risco,
                vw_dim_procedimento,
                vw_dim_diagnostico,
                vw_dim_setor_leito,
                vw_dim_tempo TO authenticated;
GRANT ALL ON TABLE dim_tempo, dim_paciente, dim_procedimento,
    dim_diagnostico, dim_setor_leito, fato_internacoes TO service_role;
GRANT SELECT ON vw_painel_executivo_mensal, vw_eficiencia_leitos_setor,
    vw_detalhe_clinico_risco, vw_dim_procedimento, vw_dim_diagnostico,
    vw_dim_setor_leito, vw_dim_tempo TO service_role;

COMMIT;


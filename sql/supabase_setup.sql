-- ==============================================================================
-- PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
-- ARQUIVO: supabase_setup.sql
-- DESCRIÇÃO: Script completo de inicialização para o banco Supabase (PostgreSQL)
-- INCLUI: Star Schema DDL, Índices, Views Analíticas de BI, RLS e Permissões de API
-- ==============================================================================

-- Garantir que estamos no schema público
SET search_path TO public;

-- ------------------------------------------------------------------------------
-- 1. LIMPEZA PREVENTIVA (Ordem reversa de dependência das FKs)
-- ------------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_detalhe_clinico_risco CASCADE;
DROP VIEW IF EXISTS vw_eficiencia_leitos_setor CASCADE;
DROP VIEW IF EXISTS vw_painel_executivo_mensal CASCADE;

DROP TABLE IF EXISTS fato_internacoes CASCADE;
DROP TABLE IF EXISTS dim_paciente CASCADE;
DROP TABLE IF EXISTS dim_procedimento CASCADE;
DROP TABLE IF EXISTS dim_diagnostico CASCADE;
DROP TABLE IF EXISTS dim_setor_leito CASCADE;
DROP TABLE IF EXISTS dim_tempo CASCADE;

-- ------------------------------------------------------------------------------
-- 2. CRIAÇÃO DAS TABELAS DIMENSIONAIS
-- ------------------------------------------------------------------------------

-- Dimensão Tempo (Calendário analítico)
CREATE TABLE dim_tempo (
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

-- Dimensão Paciente (Dados demográficos anonimizados)
CREATE TABLE dim_paciente (
    id_paciente VARCHAR(64) PRIMARY KEY,   -- Hash anônimo único
    sexo VARCHAR(1) NOT NULL,              -- 'M' ou 'F'
    idade INTEGER NOT NULL,
    faixa_etaria VARCHAR(30) NOT NULL,     -- '0-17 anos', '18-39 anos', etc.
    municipio_residencia VARCHAR(100),
    uf_residencia VARCHAR(2)
);

COMMENT ON TABLE dim_paciente IS 'Dimensão com perfil demográfico e estratificação etária dos pacientes';

-- Dimensão Procedimento (SIGTAP SUS / TUSS)
CREATE TABLE dim_procedimento (
    id_procedimento VARCHAR(12) PRIMARY KEY, -- Código SIGTAP (10 dígitos)
    descricao_procedimento VARCHAR(255) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,      -- 'Ortopedia', 'Cardiologia', etc.
    complexidade VARCHAR(30) NOT NULL,       -- 'Média Complexidade', 'Alta Complexidade'
    porte_cirurgico VARCHAR(20),            -- 'Pequeno', 'Médio', 'Grande', 'Clínico'
    tmp_protocolo_previsto NUMERIC(4, 1) NOT NULL -- Tempo médio esperado em protocolo (dias)
);

COMMENT ON TABLE dim_procedimento IS 'Catálogo de procedimentos com benchmarks de permanência (TMP) esperado';

-- Dimensão Diagnóstico (CID-10)
CREATE TABLE dim_diagnostico (
    cid_10 VARCHAR(10) PRIMARY KEY,         -- Código CID-10 (ex: 'I21.9')
    descricao_cid VARCHAR(255) NOT NULL,
    capitulo_cid VARCHAR(120) NOT NULL,     -- Capítulo da OMS
    grau_severidade VARCHAR(30) NOT NULL    -- 'Leve', 'Moderado', 'Grave', 'Crítico'
);

COMMENT ON TABLE dim_diagnostico IS 'Classificação Internacional de Doenças com estratificação de gravidade clínica';

-- Dimensão Setor e Leito (Capacidade Instalada)
CREATE TABLE dim_setor_leito (
    id_leito VARCHAR(20) PRIMARY KEY,       -- Identificador da unidade
    tipo_acomodacao VARCHAR(50) NOT NULL,   -- 'UTI Adulto & Crítica', 'Enfermaria Cirúrgica', etc.
    setor_hospitalar VARCHAR(80) NOT NULL,  -- Bloco / Pavilhão
    leitos_operacionais INTEGER NOT NULL    -- Capacidade instalada
);

COMMENT ON TABLE dim_setor_leito IS 'Mapeamento de capacidade operacional por setor e tipo de leito';

-- ------------------------------------------------------------------------------
-- 3. CRIAÇÃO DA TABELA FATO: INTERNAÇÕES HOSPITALARES
-- ------------------------------------------------------------------------------
CREATE TABLE fato_internacoes (
    id_atendimento VARCHAR(32) PRIMARY KEY, -- Número do Atendimento / AIH
    id_paciente VARCHAR(64) NOT NULL REFERENCES dim_paciente(id_paciente),
    id_procedimento VARCHAR(12) NOT NULL REFERENCES dim_procedimento(id_procedimento),
    cid_10 VARCHAR(10) NOT NULL REFERENCES dim_diagnostico(cid_10),
    id_leito VARCHAR(20) NOT NULL REFERENCES dim_setor_leito(id_leito),
    id_data_admissao INTEGER NOT NULL REFERENCES dim_tempo(id_data),
    id_data_alta INTEGER NOT NULL REFERENCES dim_tempo(id_data),
    
    -- Métricas de Permanência e Ocupação
    dias_permanencia INTEGER NOT NULL,      -- TMP individual (ALOS)
    dias_uti INTEGER DEFAULT 0,             -- Diárias em leito intensivo
    qtd_diarias INTEGER NOT NULL,
    
    -- Métricas Financeiras e Custos (R$)
    custo_hospitalar NUMERIC(12, 2) NOT NULL,       -- Hotelaria, gases, enfermagem
    custo_servicos_profissionais NUMERIC(12, 2) NOT NULL, -- Honorários médicos
    custo_opme NUMERIC(12, 2) DEFAULT 0.00,        -- Órteses, Próteses e Mat. Especiais
    custo_sadt NUMERIC(12, 2) DEFAULT 0.00,        -- Exames complementares e imagem
    custo_total NUMERIC(12, 2) NOT NULL,           -- Custo operacional direto
    receita_faturada NUMERIC(12, 2) NOT NULL,      -- Receita faturada/repassada
    margem_contribuicao NUMERIC(12, 2) NOT NULL,   -- Receita - Custo Total
    
    -- Desfechos e Indicadores de Qualidade Clínica
    status_desfecho VARCHAR(30) NOT NULL,          -- 'Alta Curado/Melhorado', 'Óbito', 'Transferido'
    indicador_obito INTEGER DEFAULT 0,             -- 1 = Óbito, 0 = Sobrevivente
    readmissao_30d BOOLEAN DEFAULT FALSE          -- Readmissão não planejada em até 30 dias
);

COMMENT ON TABLE fato_internacoes IS 'Tabela fato com histórico granular de internações, custos e desfechos clínicos';

-- ------------------------------------------------------------------------------
-- 4. ÍNDICES ANALÍTICOS (Otimização para consultas agregadas e filtros de BI)
-- ------------------------------------------------------------------------------
CREATE INDEX idx_fato_data_admissao ON fato_internacoes(id_data_admissao);
CREATE INDEX idx_fato_data_leito ON fato_internacoes(id_data_admissao, id_leito);
CREATE INDEX idx_fato_data_procedimento ON fato_internacoes(id_data_admissao, id_procedimento);
CREATE INDEX idx_fato_data_alta ON fato_internacoes(id_data_alta);
CREATE INDEX idx_fato_paciente ON fato_internacoes(id_paciente);
CREATE INDEX idx_fato_procedimento ON fato_internacoes(id_procedimento);
CREATE INDEX idx_fato_diagnostico ON fato_internacoes(cid_10);
CREATE INDEX idx_fato_leito ON fato_internacoes(id_leito);
-- readmissao_30d and indicador_obito are low-cardinality metrics aggregated
-- over the fact table; standalone B-tree indexes do not help those scans.
-- margem_contribuicao is aggregated/sorted in reports, not used as a row filter.

-- ------------------------------------------------------------------------------
-- 5. VIEWS ANALÍTICAS PARA BI E DASHBOARDS
-- ------------------------------------------------------------------------------

-- View 1: Painel Executivo Mensal (KPIs consolidados por especialidade e mês)
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

COMMENT ON VIEW vw_painel_executivo_mensal IS 'Visão executiva mensal com KPIs de receita, margem, permanência e mortalidade';

-- View 2: Eficiência e Giro de Leitos por Setor
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

COMMENT ON VIEW vw_eficiencia_leitos_setor IS 'Métricas operacionais de taxa de ocupação e giro de leitos por setor';

-- View 3: Detalhamento Clínico e Gestão de Risco
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

COMMENT ON VIEW vw_detalhe_clinico_risco IS 'Visão detalhada de pacientes, diagnósticos, desvios de protocolo e risco clínico';

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

-- Políticas de leitura apenas para usuários autenticados.
DROP POLICY IF EXISTS "Permitir leitura dim_tempo" ON dim_tempo;
DROP POLICY IF EXISTS "Permitir leitura dim_paciente" ON dim_paciente;
DROP POLICY IF EXISTS "Permitir leitura dim_procedimento" ON dim_procedimento;
DROP POLICY IF EXISTS "Permitir leitura dim_diagnostico" ON dim_diagnostico;
DROP POLICY IF EXISTS "Permitir leitura dim_setor_leito" ON dim_setor_leito;
DROP POLICY IF EXISTS "Permitir leitura fato_internacoes" ON fato_internacoes;
CREATE POLICY "Permitir leitura dim_tempo" ON dim_tempo FOR SELECT TO authenticated USING (true);
CREATE POLICY "Permitir leitura dim_paciente" ON dim_paciente FOR SELECT TO authenticated USING (true);
CREATE POLICY "Permitir leitura dim_procedimento" ON dim_procedimento FOR SELECT TO authenticated USING (true);
CREATE POLICY "Permitir leitura dim_diagnostico" ON dim_diagnostico FOR SELECT TO authenticated USING (true);
CREATE POLICY "Permitir leitura dim_setor_leito" ON dim_setor_leito FOR SELECT TO authenticated USING (true);
CREATE POLICY "Permitir leitura fato_internacoes" ON fato_internacoes FOR SELECT TO authenticated USING (true);

-- Permissões de escrita apenas para service_role (cargas de ETL/manutenção)
CREATE POLICY "Permitir insercao service_role dim_tempo" ON dim_tempo FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Permitir insercao service_role dim_paciente" ON dim_paciente FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Permitir insercao service_role dim_procedimento" ON dim_procedimento FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Permitir insercao service_role dim_diagnostico" ON dim_diagnostico FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Permitir insercao service_role dim_setor_leito" ON dim_setor_leito FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Permitir insercao service_role fato_internacoes" ON fato_internacoes FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Garantir concessão explícita de permissões para os roles do Supabase
GRANT USAGE ON SCHEMA public TO authenticated, service_role;
REVOKE ALL ON SCHEMA public FROM anon;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;


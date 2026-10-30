-- ==============================================================================
-- PROJETO: Healthcare Analytics - Gestão Hospitalar & Eficiência Assistencial
-- ARQUIVO: 01_ddl_star_schema.sql
-- DESCRIÇÃO: Criação das tabelas do Star Schema (Fato e Dimensões) e Índices
-- DIALETO: ANSI SQL compatível com PostgreSQL, DuckDB, MySQL e SQLite
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. DIMENSÃO TEMPO
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS fato_internacoes;
DROP TABLE IF EXISTS dim_paciente;
DROP TABLE IF EXISTS dim_procedimento;
DROP TABLE IF EXISTS dim_diagnostico;
DROP TABLE IF EXISTS dim_setor_leito;
DROP TABLE IF EXISTS dim_tempo;

CREATE TABLE dim_tempo (
    id_data INTEGER PRIMARY KEY,           -- Chave substituta YYYYMMDD (ex: 20230115)
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

-- ------------------------------------------------------------------------------
-- 2. DIMENSÃO PACIENTE
-- ------------------------------------------------------------------------------
CREATE TABLE dim_paciente (
    id_paciente VARCHAR(64) PRIMARY KEY,   -- Hash identificador anônimo
    sexo VARCHAR(1) NOT NULL,              -- 'M' ou 'F'
    idade INTEGER NOT NULL,
    faixa_etaria VARCHAR(30) NOT NULL,     -- '0-17 anos', '18-39 anos', '40-59 anos', '60-79 anos', '80+ anos'
    municipio_residencia VARCHAR(100),
    uf_residencia VARCHAR(2)
);

-- ------------------------------------------------------------------------------
-- 3. DIMENSÃO PROCEDIMENTO (Tabela SIGTAP do SUS / Rol ANS)
-- ------------------------------------------------------------------------------
CREATE TABLE dim_procedimento (
    id_procedimento VARCHAR(12) PRIMARY KEY, -- Código do procedimento (10 dígitos)
    descricao_procedimento VARCHAR(255) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,      -- 'Ortopedia', 'Cardiologia', 'Cirurgia Geral', etc.
    complexidade VARCHAR(30) NOT NULL,       -- 'Média Complexidade', 'Alta Complexidade'
    porte_cirurgico VARCHAR(20),            -- 'Pequeno', 'Médio', 'Grande', 'Clínico'
    tmp_protocolo_previsto NUMERIC(4, 1) NOT NULL -- Tempo médio esperado em protocolo (dias)
);

-- ------------------------------------------------------------------------------
-- 4. DIMENSÃO DIAGNÓSTICO (Classificação Internacional de Doenças - CID-10)
-- ------------------------------------------------------------------------------
CREATE TABLE dim_diagnostico (
    cid_10 VARCHAR(10) PRIMARY KEY,         -- Código CID-10 (ex: 'I21.9', 'S72.0')
    descricao_cid VARCHAR(255) NOT NULL,
    capitulo_cid VARCHAR(120) NOT NULL,     -- ex: 'Doenças do aparelho circulatório'
    grau_severidade VARCHAR(30) NOT NULL    -- 'Leve', 'Moderado', 'Grave', 'Crítico'
);

-- ------------------------------------------------------------------------------
-- 5. DIMENSÃO SETOR E LEITO (Capacidade e Alocação)
-- ------------------------------------------------------------------------------
CREATE TABLE dim_setor_leito (
    id_leito VARCHAR(20) PRIMARY KEY,       -- Identificador do setor/unidade
    tipo_acomodacao VARCHAR(50) NOT NULL,   -- 'UTI Adulto', 'UTI Neonatal', 'Enfermaria Cirúrgica', 'Enfermaria Clínica'
    setor_hospitalar VARCHAR(80) NOT NULL,  -- 'Bloco A', 'Bloco B', 'Pavilhão Crítico'
    leitos_operacionais INTEGER NOT NULL    -- Capacidade instalada do setor
);

-- ------------------------------------------------------------------------------
-- 6. TABELA FATO: INTERNAÇÕES HOSPITALARES
-- ------------------------------------------------------------------------------
CREATE TABLE fato_internacoes (
    id_atendimento VARCHAR(32) PRIMARY KEY, -- Número da AIH / Atendimento
    id_paciente VARCHAR(64) NOT NULL,
    id_procedimento VARCHAR(12) NOT NULL,
    cid_10 VARCHAR(10) NOT NULL,
    id_leito VARCHAR(20) NOT NULL,
    id_data_admissao INTEGER NOT NULL,
    id_data_alta INTEGER NOT NULL,
    
    -- Métricas de Permanência e Ocupação
    dias_permanencia INTEGER NOT NULL,      -- TMP do paciente
    dias_uti INTEGER DEFAULT 0,             -- Tempo em leito intensivo
    qtd_diarias INTEGER NOT NULL,
    
    -- Métricas Financeiras e Custos (R$)
    custo_hospitalar NUMERIC(12, 2) NOT NULL,       -- VAL_SH (Hotelaria, Enfermagem)
    custo_servicos_profissionais NUMERIC(12, 2) NOT NULL, -- VAL_SP (Honorários médicos)
    custo_opme NUMERIC(12, 2) DEFAULT 0.00,        -- VAL_ORTP (Órteses, Próteses e Materiais Especiais)
    custo_sadt NUMERIC(12, 2) DEFAULT 0.00,        -- VAL_SADT (Exames complementares e imagem)
    custo_total NUMERIC(12, 2) NOT NULL,           -- Custo operacional direto total
    receita_faturada NUMERIC(12, 2) NOT NULL,      -- VAL_TOT (Valor total repassado/faturado)
    margem_contribuicao NUMERIC(12, 2) NOT NULL,   -- receita_faturada - custo_total
    
    -- Desfechos e Indicadores de Qualidade Clínica
    status_desfecho VARCHAR(30) NOT NULL,          -- 'Alta Curado', 'Alta Melhorado', 'Óbito', 'Transferido'
    indicador_obito INTEGER DEFAULT 0,             -- 1 = Óbito, 0 = Sobrevivente
    readmissao_30d BOOLEAN DEFAULT FALSE,          -- Reinternação em até 30 dias pela mesma patologia
    
    -- Chaves Estrangeiras
    CONSTRAINT fk_paciente FOREIGN KEY (id_paciente) REFERENCES dim_paciente(id_paciente),
    CONSTRAINT fk_procedimento FOREIGN KEY (id_procedimento) REFERENCES dim_procedimento(id_procedimento),
    CONSTRAINT fk_diagnostico FOREIGN KEY (cid_10) REFERENCES dim_diagnostico(cid_10),
    CONSTRAINT fk_leito FOREIGN KEY (id_leito) REFERENCES dim_setor_leito(id_leito),
    CONSTRAINT fk_data_admissao FOREIGN KEY (id_data_admissao) REFERENCES dim_tempo(id_data),
    CONSTRAINT fk_data_alta FOREIGN KEY (id_data_alta) REFERENCES dim_tempo(id_data)
);

-- ------------------------------------------------------------------------------
-- 7. ÍNDICES ANALÍTICOS (Para acelerar consultas de BI e agregações)
-- ------------------------------------------------------------------------------
CREATE INDEX idx_fato_data_admissao ON fato_internacoes(id_data_admissao);
CREATE INDEX idx_fato_procedimento ON fato_internacoes(id_procedimento);
CREATE INDEX idx_fato_diagnostico ON fato_internacoes(cid_10);
CREATE INDEX idx_fato_leito ON fato_internacoes(id_leito);
CREATE INDEX idx_fato_readmissao ON fato_internacoes(readmissao_30d);
CREATE INDEX idx_fato_margem ON fato_internacoes(margem_contribuicao);

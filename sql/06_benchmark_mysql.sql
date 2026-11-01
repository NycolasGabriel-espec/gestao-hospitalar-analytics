-- Camada agregada do benchmark sintético para o dashboard autenticado na Vercel.
-- Nenhuma tabela clínica/SIH-SUS é alterada por esta migração.

CREATE TABLE IF NOT EXISTS benchmark_resumo_mensal (
    ano_mes VARCHAR(7) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,
    id_leito VARCHAR(20) NOT NULL,
    setor_hospitalar VARCHAR(80) NOT NULL,
    leitos_operacionais INT NOT NULL,
    volume_internacoes INT NOT NULL,
    espera_media_minutos DECIMAL(8,2) NOT NULL,
    custo_hospitalar DECIMAL(14,2) NOT NULL,
    custo_servicos_profissionais DECIMAL(14,2) NOT NULL,
    custo_opme DECIMAL(14,2) NOT NULL,
    custo_sadt DECIMAL(14,2) NOT NULL,
    custo_total DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (ano_mes, especialidade, id_leito),
    KEY idx_benchmark_resumo_especialidade (especialidade, ano_mes),
    KEY idx_benchmark_resumo_setor (id_leito, ano_mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Agregados mensais de espera e custos do benchmark sintético';

CREATE TABLE IF NOT EXISTS benchmark_ocupacao_mensal (
    ano_mes VARCHAR(7) NOT NULL,
    id_leito VARCHAR(20) NOT NULL,
    setor_hospitalar VARCHAR(80) NOT NULL,
    leitos_operacionais INT NOT NULL,
    dias_paciente INT NOT NULL,
    leitos_dia_disponiveis INT NOT NULL,
    ocupacao_pct DECIMAL(7,2) NOT NULL,
    PRIMARY KEY (ano_mes, id_leito)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Ocupação mensal reconstruída somente para o benchmark sintético';

CREATE TABLE IF NOT EXISTS benchmark_custos_procedimento (
    ano_mes VARCHAR(7) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,
    id_leito VARCHAR(20) NOT NULL,
    setor_hospitalar VARCHAR(80) NOT NULL,
    id_procedimento VARCHAR(12) NOT NULL,
    descricao_procedimento VARCHAR(255) NOT NULL,
    custo_hospitalar DECIMAL(14,2) NOT NULL,
    custo_servicos_profissionais DECIMAL(14,2) NOT NULL,
    custo_opme DECIMAL(14,2) NOT NULL,
    custo_sadt DECIMAL(14,2) NOT NULL,
    custo_total DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (ano_mes, id_procedimento, id_leito, especialidade),
    KEY idx_benchmark_custos_especialidade (especialidade, ano_mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Custos simulados agregados por procedimento, mês e setor de destino';

CREATE TABLE IF NOT EXISTS benchmark_chegadas_hora (
    dia_semana TINYINT UNSIGNED NOT NULL,
    nome_dia VARCHAR(12) NOT NULL,
    hora TINYINT UNSIGNED NOT NULL,
    volume_chegadas INT UNSIGNED NOT NULL,
    PRIMARY KEY (dia_semana, hora)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Chegadas sintéticas agrupadas por dia da semana e hora';

CREATE TABLE IF NOT EXISTS benchmark_metadata (
    id TINYINT UNSIGNED NOT NULL,
    num_admissoes INT UNSIGNED NOT NULL,
    seed INT NOT NULL,
    ano_chegada SMALLINT UNSIGNED NOT NULL,
    leitos_operacionais SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT chk_benchmark_metadata_singleton CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Metadados da geração do benchmark sintético';

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_benchmark_resumo_mensal AS
SELECT ano_mes, especialidade, id_leito, setor_hospitalar, leitos_operacionais,
       volume_internacoes, espera_media_minutos, custo_hospitalar,
       custo_servicos_profissionais, custo_opme, custo_sadt, custo_total
FROM benchmark_resumo_mensal;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_benchmark_ocupacao_mensal AS
SELECT ano_mes, id_leito, setor_hospitalar, leitos_operacionais,
       dias_paciente, leitos_dia_disponiveis, ocupacao_pct
FROM benchmark_ocupacao_mensal;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_benchmark_custos_procedimento AS
SELECT ano_mes, especialidade, id_leito, setor_hospitalar, id_procedimento, descricao_procedimento,
       custo_hospitalar, custo_servicos_profissionais, custo_opme, custo_sadt, custo_total
FROM benchmark_custos_procedimento;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_benchmark_chegadas_hora AS
SELECT dia_semana, nome_dia, hora, volume_chegadas
FROM benchmark_chegadas_hora;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_benchmark_metadata AS
SELECT num_admissoes, seed, ano_chegada, leitos_operacionais
FROM benchmark_metadata
WHERE id = 1;

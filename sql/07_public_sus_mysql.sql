-- Agregados públicos reais: SIH/SUS, CNES e fila SISREG estadual.
-- Nenhuma AIH, pessoa, CNS ou código de solicitação é armazenado nesta camada.

CREATE TABLE IF NOT EXISTS sih_publico_aih_mensal (
    ano_mes VARCHAR(7) NOT NULL,
    volume_aih INT UNSIGNED NOT NULL,
    dias_permanencia INT UNSIGNED NULL,
    permanencia_media_dias DECIMAL(7,1) NULL,
    valor_aih_total DECIMAL(16,2) NULL,
    aihs_com_valor INT UNSIGNED NOT NULL,
    PRIMARY KEY (ano_mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Agregados estaduais SIH por mês de admissão; sem identificadores de AIH';

CREATE TABLE IF NOT EXISTS sih_publico_aih_procedimento (
    ano_mes VARCHAR(7) NOT NULL,
    id_procedimento VARCHAR(12) NOT NULL,
    volume_aih INT UNSIGNED NOT NULL,
    dias_permanencia INT UNSIGNED NULL,
    permanencia_media_dias DECIMAL(7,1) NULL,
    valor_aih_total DECIMAL(16,2) NULL,
    aihs_com_valor INT UNSIGNED NOT NULL,
    PRIMARY KEY (ano_mes, id_procedimento),
    KEY idx_sih_aih_procedimento (id_procedimento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Agregados SIH por mês de admissão/procedimento; sem identificadores de AIH';

CREATE TABLE IF NOT EXISTS cnes_leitos_publicos_mensal (
    ano_mes VARCHAR(7) NOT NULL,
    uf CHAR(2) NOT NULL,
    estabelecimentos_hospitalares INT UNSIGNED NOT NULL,
    leitos_gerais_sus INT UNSIGNED NOT NULL,
    leitos_uti_sus INT UNSIGNED NOT NULL,
    total_leitos_sus INT UNSIGNED NOT NULL,
    PRIMARY KEY (ano_mes, uf)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Somas mensais de leitos CNES publicados, sem dados por estabelecimento';

CREATE TABLE IF NOT EXISTS sih_ocupacao_estimada_mensal (
    ano_mes VARCHAR(7) NOT NULL,
    dias_paciente_sih INT UNSIGNED NOT NULL,
    leitos_sus_cnes INT UNSIGNED NOT NULL,
    leitos_dia_disponiveis INT UNSIGNED NOT NULL,
    ocupacao_estimada_pct DECIMAL(7,2) NOT NULL,
    PRIMARY KEY (ano_mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Proxy mensal SIH/CNES; não representa censo hospitalar observado';

CREATE TABLE IF NOT EXISTS sisreg_fila_publica_procedimento (
    data_extracao DATE NOT NULL,
    procedimento VARCHAR(255) NOT NULL,
    solicitacoes_pendentes INT UNSIGNED NOT NULL,
    espera_media_dias INT UNSIGNED NOT NULL,
    espera_mediana_dias INT UNSIGNED NOT NULL,
    espera_p90_dias INT UNSIGNED NOT NULL,
    espera_max_dias INT UNSIGNED NOT NULL,
    PRIMARY KEY (data_extracao, procedimento),
    KEY idx_sisreg_fila_p90 (data_extracao, espera_p90_dias)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Fila SISREG agregada por procedimento; sem identificadores ou linhas individuais';

CREATE TABLE IF NOT EXISTS public_sus_dataset_manifest (
    source_key VARCHAR(24) NOT NULL,
    source_label VARCHAR(80) NOT NULL,
    source_url VARCHAR(500) NOT NULL,
    data_through DATE NULL,
    coverage_start DATE NULL,
    coverage_end DATE NULL,
    source_record_count BIGINT UNSIGNED NOT NULL,
    aggregate_row_count INT UNSIGNED NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    loaded_at_utc DATETIME(6) NOT NULL,
    PRIMARY KEY (source_key),
    CONSTRAINT chk_public_sus_manifest_coverage
        CHECK (coverage_start IS NULL OR coverage_end IS NULL OR coverage_start <= coverage_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Proveniência, cobertura, integridade e horário de carga das fontes públicas';

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_sus_sih_mensal AS
SELECT
    ano_mes, volume_aih, dias_permanencia, permanencia_media_dias,
    valor_aih_total, aihs_com_valor
FROM sih_publico_aih_mensal
WHERE ano_mes LIKE '2025-%';

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_sus_sih_procedimento_mensal AS
SELECT
    ano_mes, id_procedimento, volume_aih, permanencia_media_dias,
    valor_aih_total, aihs_com_valor
FROM sih_publico_aih_procedimento
WHERE ano_mes LIKE '2025-%';

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_sus_sih_procedimento_anual AS
SELECT
    ano_mes, id_procedimento, volume_aih, permanencia_media_dias,
    valor_aih_total, aihs_com_valor
FROM sih_publico_aih_procedimento
WHERE ano_mes = '2025';

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_cnes_leitos_mensal AS
SELECT ano_mes, uf, estabelecimentos_hospitalares, leitos_gerais_sus,
       leitos_uti_sus, total_leitos_sus
FROM cnes_leitos_publicos_mensal;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_sih_ocupacao_estimada_mensal AS
SELECT ano_mes, dias_paciente_sih, leitos_sus_cnes,
       leitos_dia_disponiveis, ocupacao_estimada_pct
FROM sih_ocupacao_estimada_mensal;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_sisreg_fila_procedimento AS
SELECT data_extracao, procedimento, solicitacoes_pendentes,
       espera_media_dias, espera_mediana_dias, espera_p90_dias, espera_max_dias
FROM sisreg_fila_publica_procedimento;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_public_sus_dataset_manifest AS
SELECT source_key, source_label, data_through, coverage_start, coverage_end,
       source_record_count, aggregate_row_count, loaded_at_utc
FROM public_sus_dataset_manifest;

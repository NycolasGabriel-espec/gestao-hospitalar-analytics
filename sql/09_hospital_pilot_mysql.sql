-- Camada isolada para um piloto hospitalar; não é usada pela API Vercel atual.
-- Execute como DBA. Não conceda acesso dessas tabelas às contas dashboard_app
-- ou powerbi_reader antes de implementar autorização por hospital/tenant.

CREATE DATABASE IF NOT EXISTS hospital_pilot
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS hospital_pilot.pilot_hospital_registry (
    hospital_id VARCHAR(64) NOT NULL,
    cnes_code CHAR(7) NULL,
    display_name VARCHAR(160) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (hospital_id),
    UNIQUE KEY uq_pilot_hospital_cnes (cnes_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Registro de unidades do piloto; sem dados de pacientes';

CREATE TABLE IF NOT EXISTS hospital_pilot.pilot_bed_census_daily (
    hospital_id VARCHAR(64) NOT NULL,
    observation_date DATE NOT NULL,
    shift_code VARCHAR(16) NOT NULL,
    sector_code VARCHAR(64) NOT NULL,
    bed_type VARCHAR(32) NOT NULL,
    operational_beds INT UNSIGNED NOT NULL,
    staffed_beds INT UNSIGNED NOT NULL,
    occupied_beds INT UNSIGNED NOT NULL,
    blocked_beds INT UNSIGNED NOT NULL,
    imported_at_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (hospital_id, observation_date, shift_code, sector_code, bed_type),
    KEY idx_pilot_bed_date_sector (observation_date, hospital_id, sector_code),
    CONSTRAINT fk_pilot_bed_hospital
        FOREIGN KEY (hospital_id) REFERENCES hospital_pilot.pilot_hospital_registry(hospital_id),
    CONSTRAINT chk_pilot_staffed_beds CHECK (staffed_beds <= operational_beds),
    CONSTRAINT chk_pilot_blocked_beds CHECK (blocked_beds <= operational_beds)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Censo agregado por turno e setor; não contém paciente ou atendimento';

CREATE TABLE IF NOT EXISTS hospital_pilot.pilot_admissions_monthly (
    hospital_id VARCHAR(64) NOT NULL,
    ano_mes CHAR(7) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,
    id_procedimento VARCHAR(12) NOT NULL,
    volume_admissoes INT UNSIGNED NOT NULL,
    volume_altas INT UNSIGNED NOT NULL,
    dias_paciente INT UNSIGNED NOT NULL,
    imported_at_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (hospital_id, ano_mes, especialidade, id_procedimento),
    KEY idx_pilot_admissions_month (ano_mes, hospital_id),
    CONSTRAINT fk_pilot_admissions_hospital
        FOREIGN KEY (hospital_id) REFERENCES hospital_pilot.pilot_hospital_registry(hospital_id),
    CONSTRAINT chk_pilot_admissions_month
        CHECK (ano_mes REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Totais mensais sem chave de pessoa; não permite estimar readmissão';

CREATE TABLE IF NOT EXISTS hospital_pilot.pilot_financial_monthly (
    hospital_id VARCHAR(64) NOT NULL,
    ano_mes CHAR(7) NOT NULL,
    centro_custo VARCHAR(80) NOT NULL,
    id_procedimento VARCHAR(12) NOT NULL,
    receita_recebida DECIMAL(16,2) NOT NULL,
    custo_hospitalar DECIMAL(16,2) NOT NULL,
    custo_servicos_profissionais DECIMAL(16,2) NOT NULL,
    custo_opme DECIMAL(16,2) NOT NULL,
    custo_sadt DECIMAL(16,2) NOT NULL,
    imported_at_utc DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (hospital_id, ano_mes, centro_custo, id_procedimento),
    KEY idx_pilot_financial_month (ano_mes, hospital_id),
    CONSTRAINT fk_pilot_financial_hospital
        FOREIGN KEY (hospital_id) REFERENCES hospital_pilot.pilot_hospital_registry(hospital_id),
    CONSTRAINT chk_pilot_financial_month
        CHECK (ano_mes REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Totais contábeis mensais; valores negativos podem representar ajustes';

CREATE TABLE IF NOT EXISTS hospital_pilot.pilot_source_manifest (
    hospital_id VARCHAR(64) NOT NULL,
    source_key VARCHAR(32) NOT NULL,
    source_label VARCHAR(100) NOT NULL,
    coverage_start DATE NULL,
    coverage_end DATE NULL,
    source_record_count BIGINT UNSIGNED NOT NULL,
    aggregate_row_count INT UNSIGNED NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    loaded_at_utc DATETIME(6) NOT NULL,
    PRIMARY KEY (hospital_id, source_key),
    CONSTRAINT fk_pilot_manifest_hospital
        FOREIGN KEY (hospital_id) REFERENCES hospital_pilot.pilot_hospital_registry(hospital_id),
    CONSTRAINT chk_pilot_manifest_coverage
        CHECK (coverage_start IS NULL OR coverage_end IS NULL OR coverage_start <= coverage_end)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Proveniência das cargas agregadas de cada unidade do piloto';

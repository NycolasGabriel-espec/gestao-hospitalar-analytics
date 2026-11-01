-- MySQL 8.0+ schema for Hospital Analytics.
-- Run as a schema owner/admin. App credentials should receive only the grants
-- listed in docs/mysql_integration.md; do not give the web app base-table access.

CREATE TABLE IF NOT EXISTS dim_tempo (
    id_data INT NOT NULL,
    data_completa DATE NOT NULL,
    ano INT NOT NULL,
    mes INT NOT NULL,
    dia INT NOT NULL,
    nome_mes VARCHAR(20) NOT NULL,
    trimestre INT NOT NULL,
    ano_mes VARCHAR(7) NOT NULL,
    dia_semana VARCHAR(20) NOT NULL,
    eh_fim_semana TINYINT(1) NOT NULL,
    PRIMARY KEY (id_data),
    KEY idx_dim_tempo_ano_mes (ano_mes)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Calendário analítico detalhado por dia';

CREATE TABLE IF NOT EXISTS dim_paciente (
    id_paciente VARCHAR(64) NOT NULL,
    sexo VARCHAR(1) NOT NULL,
    faixa_etaria VARCHAR(30) NOT NULL,
    PRIMARY KEY (id_paciente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Dimensão pseudonimizada sem idade exata ou município';

CREATE TABLE IF NOT EXISTS dim_procedimento (
    id_procedimento VARCHAR(12) NOT NULL,
    descricao_procedimento VARCHAR(255) NOT NULL,
    especialidade VARCHAR(80) NOT NULL,
    complexidade VARCHAR(30) NOT NULL,
    porte_cirurgico VARCHAR(20) NULL,
    tmp_protocolo_previsto DECIMAL(4,1) NULL,
    PRIMARY KEY (id_procedimento),
    KEY idx_dim_procedimento_especialidade (especialidade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Catálogo de procedimentos; TMP só deve vir de protocolo validado';

CREATE TABLE IF NOT EXISTS dim_diagnostico (
    cid_10 VARCHAR(10) NOT NULL,
    descricao_cid VARCHAR(255) NOT NULL,
    capitulo_cid VARCHAR(120) NOT NULL,
    grau_severidade VARCHAR(30) NOT NULL,
    PRIMARY KEY (cid_10),
    KEY idx_dim_diagnostico_severidade (grau_severidade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Códigos CID-10; severidade não é inferida automaticamente do código';

CREATE TABLE IF NOT EXISTS dim_setor_leito (
    id_leito VARCHAR(20) NOT NULL,
    tipo_acomodacao VARCHAR(50) NOT NULL,
    setor_hospitalar VARCHAR(80) NOT NULL,
    leitos_operacionais INT NULL,
    PRIMARY KEY (id_leito)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Capacidade por setor quando informada pela fonte';

CREATE TABLE IF NOT EXISTS fato_internacoes (
    id_atendimento VARCHAR(64) NOT NULL,
    id_paciente VARCHAR(64) NOT NULL,
    id_procedimento VARCHAR(12) NOT NULL,
    cid_10 VARCHAR(10) NOT NULL,
    id_leito VARCHAR(20) NOT NULL,
    id_data_admissao INT NOT NULL,
    id_data_alta INT NULL,
    dias_permanencia INT NULL,
    dias_uti INT NULL,
    qtd_diarias INT NULL,
    custo_hospitalar DECIMAL(12,2) NULL,
    custo_servicos_profissionais DECIMAL(12,2) NULL,
    custo_opme DECIMAL(12,2) NULL,
    custo_sadt DECIMAL(12,2) NULL,
    custo_total DECIMAL(12,2) NULL,
    receita_faturada DECIMAL(12,2) NULL,
    margem_contribuicao DECIMAL(12,2) NULL,
    status_desfecho VARCHAR(80) NULL,
    indicador_obito INT NULL,
    readmissao_30d TINYINT(1) NULL,
    PRIMARY KEY (id_atendimento),
    KEY idx_fato_data_admissao (id_data_admissao),
    KEY idx_fato_data_leito (id_data_admissao, id_leito),
    KEY idx_fato_data_procedimento (id_data_admissao, id_procedimento),
    KEY idx_fato_data_alta (id_data_alta),
    KEY idx_fato_paciente (id_paciente),
    KEY idx_fato_procedimento (id_procedimento),
    KEY idx_fato_diagnostico (cid_10),
    KEY idx_fato_leito (id_leito),
    CONSTRAINT fk_fato_paciente FOREIGN KEY (id_paciente) REFERENCES dim_paciente(id_paciente),
    CONSTRAINT fk_fato_procedimento FOREIGN KEY (id_procedimento) REFERENCES dim_procedimento(id_procedimento),
    CONSTRAINT fk_fato_diagnostico FOREIGN KEY (cid_10) REFERENCES dim_diagnostico(cid_10),
    CONSTRAINT fk_fato_leito FOREIGN KEY (id_leito) REFERENCES dim_setor_leito(id_leito),
    CONSTRAINT fk_fato_data_admissao FOREIGN KEY (id_data_admissao) REFERENCES dim_tempo(id_data),
    CONSTRAINT fk_fato_data_alta FOREIGN KEY (id_data_alta) REFERENCES dim_tempo(id_data)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Fatos granulares pseudonimizados; não conceder leitura direta à aplicação';

CREATE TABLE IF NOT EXISTS app_users (
    id CHAR(36) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    hospital_analytics_access TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_app_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Contas de acesso ao dashboard; senhas armazenadas com scrypt';

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_hash BINARY(32) NOT NULL,
    user_id CHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    PRIMARY KEY (session_hash),
    KEY idx_auth_sessions_user_expiry (user_id, expires_at),
    CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Sessões opacas; somente o hash SHA-256 do token é persistido';

CREATE TABLE IF NOT EXISTS auth_login_attempts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email_digest BINARY(32) NOT NULL,
    ip_digest BINARY(32) NOT NULL,
    succeeded TINYINT(1) NOT NULL DEFAULT 0,
    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_login_email_time (email_digest, attempted_at),
    KEY idx_login_ip_time (ip_digest, attempted_at),
    KEY idx_login_attempt_time (attempted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='Contagem de tentativas sem armazenar e-mail ou IP em claro';

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_painel_executivo_mensal AS
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
         ELSE ROUND(SUM(f.margem_contribuicao) / NULLIF(SUM(f.receita_faturada), 0) * 100, 2)
    END AS margem_pct,
    CASE WHEN COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
         ELSE ROUND(AVG(f.dias_permanencia), 1) END AS tmp_medio,
    ROUND(SUM(CASE WHEN f.readmissao_30d = 1 THEN 1 ELSE 0 END) * 100.0 /
          NULLIF(COUNT(f.readmissao_30d), 0), 2) AS taxa_readmissao_pct,
    ROUND(SUM(f.indicador_obito) * 100.0 /
          NULLIF(COUNT(f.indicador_obito), 0), 2) AS taxa_mortalidade_pct
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_procedimento p ON f.id_procedimento = p.id_procedimento
GROUP BY t.ano_mes, t.ano, t.mes, t.nome_mes, p.especialidade
HAVING COUNT(f.id_atendimento) >= 10;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_eficiencia_leitos_setor AS
SELECT
    t.ano_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais,
    COUNT(f.id_atendimento) AS total_admissoes,
    CASE WHEN COUNT(f.dias_permanencia) < COUNT(f.id_atendimento) THEN NULL
         ELSE SUM(f.dias_permanencia) END AS dias_permanencia_coorte,
    CASE WHEN COUNT(f.dias_uti) < COUNT(f.id_atendimento) THEN NULL
         ELSE SUM(f.dias_uti) END AS dias_uti_reportados_coorte,
    l.leitos_operacionais * COUNT(DISTINCT t.dia) AS leitos_dia_teoricos,
    CAST(NULL AS DECIMAL(7,2)) AS taxa_ocupacao_pct,
    ROUND(COUNT(f.id_atendimento) / NULLIF(l.leitos_operacionais, 0), 2) AS admissoes_por_leito_aproximado
FROM fato_internacoes f
JOIN dim_tempo t ON f.id_data_admissao = t.id_data
JOIN dim_setor_leito l ON f.id_leito = l.id_leito
GROUP BY t.ano_mes, l.id_leito, l.tipo_acomodacao, l.setor_hospitalar, l.leitos_operacionais
HAVING COUNT(f.id_atendimento) >= 10;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_detalhe_clinico_risco AS
SELECT
    t.ano_mes, d.cid_10, d.descricao_cid, d.grau_severidade,
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
GROUP BY t.ano_mes, d.cid_10, d.descricao_cid, d.grau_severidade,
         p.especialidade, p.descricao_procedimento, pac.faixa_etaria
HAVING COUNT(f.id_atendimento) >= 10;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_dim_procedimento AS
SELECT id_procedimento, descricao_procedimento, especialidade, complexidade, tmp_protocolo_previsto
FROM dim_procedimento;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_dim_diagnostico AS
SELECT cid_10, descricao_cid, capitulo_cid, grau_severidade
FROM dim_diagnostico;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_dim_setor_leito AS
SELECT id_leito, tipo_acomodacao, setor_hospitalar, leitos_operacionais
FROM dim_setor_leito;

CREATE OR REPLACE SQL SECURITY DEFINER VIEW vw_dim_tempo AS
SELECT ano_mes, ano, mes, nome_mes
FROM dim_tempo;

-- Create the application and ETL users separately. Do not grant the app user
-- access to fato_internacoes or dim_paciente. See docs/mysql_integration.md.

-- Execute como administrador depois de sql/mysql_setup.sql.
-- Troque hospital_analytics e as três senhas por valores próprios.
-- Não coloque a senha administrativa na Vercel.

CREATE USER IF NOT EXISTS 'dashboard_app'@'%' IDENTIFIED BY 'TROQUE_POR_UMA_SENHA_FORTE';
CREATE USER IF NOT EXISTS 'analytics_loader'@'%' IDENTIFIED BY 'TROQUE_POR_OUTRA_SENHA_FORTE';
CREATE USER IF NOT EXISTS 'powerbi_reader'@'%' IDENTIFIED BY 'TROQUE_POR_UMA_SENHA_FORTE';

-- Recomece dos privilégios diretos mínimos ao reaplicar este arquivo.
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'dashboard_app'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'analytics_loader'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'powerbi_reader'@'%';

-- A conta web acessa apenas os agregados e campos mínimos de autenticação.
GRANT SELECT ON hospital_analytics.vw_painel_executivo_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_eficiencia_leitos_setor TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_detalhe_clinico_risco TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_procedimento TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_diagnostico TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_setor_leito TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_tempo TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_resumo_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_ocupacao_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_custos_procedimento TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_chegadas_hora TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_metadata TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_sih_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_sih_procedimento_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_sih_procedimento_anual TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_cnes_leitos_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sih_ocupacao_estimada_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sisreg_fila_procedimento TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_dataset_manifest TO 'dashboard_app'@'%';
GRANT SELECT (id, email, password_hash, hospital_analytics_access)
    ON hospital_analytics.app_users TO 'dashboard_app'@'%';
GRANT UPDATE (password_hash)
    ON hospital_analytics.app_users TO 'dashboard_app'@'%';
GRANT SELECT, INSERT, DELETE ON hospital_analytics.auth_sessions TO 'dashboard_app'@'%';
GRANT SELECT, INSERT, DELETE ON hospital_analytics.auth_login_attempts TO 'dashboard_app'@'%';

-- Conta ETL, usada somente em processo local controlado.
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.dim_tempo TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.dim_paciente TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.dim_procedimento TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.dim_diagnostico TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.dim_setor_leito TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.fato_internacoes TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.benchmark_resumo_mensal TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.benchmark_ocupacao_mensal TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.benchmark_custos_procedimento TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.benchmark_chegadas_hora TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.benchmark_metadata TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.sih_publico_aih_mensal TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.sih_publico_aih_procedimento TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.cnes_leitos_publicos_mensal TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.sih_ocupacao_estimada_mensal TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.sisreg_fila_publica_procedimento TO 'analytics_loader'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hospital_analytics.public_sus_dataset_manifest TO 'analytics_loader'@'%';

-- Conta para Power BI; não conceda acesso às tabelas granulares.
GRANT SELECT ON hospital_analytics.vw_painel_executivo_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_eficiencia_leitos_setor TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_detalhe_clinico_risco TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_procedimento TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_diagnostico TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_setor_leito TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_tempo TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_resumo_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_ocupacao_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_custos_procedimento TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_chegadas_hora TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_benchmark_metadata TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_sih_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_sih_procedimento_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_sih_procedimento_anual TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_cnes_leitos_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sih_ocupacao_estimada_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sisreg_fila_procedimento TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_public_sus_dataset_manifest TO 'powerbi_reader'@'%';

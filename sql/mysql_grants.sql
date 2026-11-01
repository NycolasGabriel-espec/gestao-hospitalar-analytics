-- Execute como administrador depois de sql/mysql_setup.sql.
-- Troque hospital_analytics e as três senhas por valores próprios.
-- Não coloque a senha administrativa na Vercel.

CREATE USER IF NOT EXISTS 'dashboard_app'@'%' IDENTIFIED BY 'TROQUE_POR_UMA_SENHA_FORTE';
CREATE USER IF NOT EXISTS 'analytics_loader'@'%' IDENTIFIED BY 'TROQUE_POR_OUTRA_SENHA_FORTE';
CREATE USER IF NOT EXISTS 'powerbi_reader'@'%' IDENTIFIED BY 'TROQUE_POR_UMA_SENHA_FORTE';

-- A conta web acessa apenas os agregados e campos mínimos de autenticação.
GRANT SELECT ON hospital_analytics.vw_painel_executivo_mensal TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_eficiencia_leitos_setor TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_detalhe_clinico_risco TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_procedimento TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_diagnostico TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_setor_leito TO 'dashboard_app'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_tempo TO 'dashboard_app'@'%';
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

-- Conta para Power BI; não conceda acesso às tabelas granulares.
GRANT SELECT ON hospital_analytics.vw_painel_executivo_mensal TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_eficiencia_leitos_setor TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_detalhe_clinico_risco TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_procedimento TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_diagnostico TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_setor_leito TO 'powerbi_reader'@'%';
GRANT SELECT ON hospital_analytics.vw_dim_tempo TO 'powerbi_reader'@'%';

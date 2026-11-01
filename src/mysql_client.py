"""Cliente local somente leitura para diagnóstico e views agregadas MySQL."""

import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

VIEWS = {
    "vw_painel_executivo_mensal": {"ano_mes", "ano", "mes", "nome_mes", "especialidade", "volume_internacoes", "receita_total", "custo_total", "custo_opme", "margem_contribuicao", "margem_pct", "tmp_medio", "taxa_readmissao_pct", "taxa_mortalidade_pct"},
    "vw_eficiencia_leitos_setor": {"ano_mes", "id_leito", "tipo_acomodacao", "setor_hospitalar", "leitos_operacionais", "total_admissoes", "dias_permanencia_coorte", "dias_uti_reportados_coorte", "leitos_dia_teoricos", "taxa_ocupacao_pct", "admissoes_por_leito_aproximado"},
    "vw_detalhe_clinico_risco": {"ano_mes", "cid_10", "descricao_cid", "grau_severidade", "especialidade", "descricao_procedimento", "faixa_etaria", "volume_internacoes", "tmp_medio", "custo_medio", "taxa_mortalidade_pct", "taxa_readmissao_pct"},
    "vw_dim_procedimento": {"id_procedimento", "descricao_procedimento", "especialidade", "complexidade", "tmp_protocolo_previsto"},
    "vw_dim_diagnostico": {"cid_10", "descricao_cid", "capitulo_cid", "grau_severidade"},
    "vw_dim_setor_leito": {"id_leito", "tipo_acomodacao", "setor_hospitalar", "leitos_operacionais"},
    "vw_dim_tempo": {"ano_mes", "ano", "mes", "nome_mes"},
}


def _engine():
    configured_url = os.getenv("MYSQL_URL", "").strip()
    try:
        parsed = urlparse(configured_url)
    except ValueError as error:
        raise ValueError("MYSQL_URL não é uma URL válida.") from error
    if parsed.scheme not in {"mysql", "mysql+pymysql"} or not parsed.hostname:
        raise ValueError("Configure MYSQL_URL com uma conexão MySQL válida.")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and os.getenv("MYSQL_TLS") != "true":
        raise ValueError("MYSQL_TLS=true é obrigatório para conexões remotas.")
    connect_args = {}
    if os.getenv("MYSQL_TLS") == "true":
        ca_file = os.getenv("MYSQL_SSL_CA_FILE")
        connect_args.update(ssl_verify_cert=True, ssl_verify_identity=True)
        if ca_file:
            connect_args["ssl_ca"] = ca_file
    return create_engine(
        make_url(configured_url).set(drivername="mysql+pymysql"),
        connect_args=connect_args,
        pool_pre_ping=True,
    )


def test_mysql_connection():
    engine = _engine()
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT VERSION()")).scalar_one()
            views = {}
            for name in VIEWS:
                try:
                    views[name] = int(connection.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar_one())
                except Exception:
                    views[name] = None
            return {"success": all(value is not None for value in views.values()), "version": version, "views": views}
    finally:
        engine.dispose()


def query_view(view: str, columns: list[str] | None = None, filters: dict[str, str] | None = None, limit: int = 1000):
    if view not in VIEWS:
        raise ValueError("A consulta só pode acessar as views aprovadas.")
    selected = columns or sorted(VIEWS[view])
    if not selected or any(column not in VIEWS[view] for column in selected):
        raise ValueError("Colunas inválidas para a view.")
    if not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit deve ficar entre 1 e 1000.")
    filters = filters or {}
    if any(column not in VIEWS[view] for column in filters):
        raise ValueError("Filtro inválido para a view.")
    clauses = [f"`{column}` = :{column}" for column in filters]
    sql = f"SELECT {', '.join(f'`{column}`' for column in selected)} FROM `{view}`"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " LIMIT :limit"
    engine = _engine()
    try:
        return pd.read_sql(text(sql), engine, params={**filters, "limit": limit})
    finally:
        engine.dispose()


if __name__ == "__main__":
    print(test_mysql_connection())

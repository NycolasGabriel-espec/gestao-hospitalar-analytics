"""Carga idempotente do Star Schema local para MySQL 8+ usando uma role ETL."""

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
load_dotenv(PROJECT_ROOT / ".env")

TABLE_CONFIG = [
    ("dim_tempo", "dim_tempo.csv", "id_data", {
        "id_data": "int64", "data_completa": "string", "ano": "int64", "mes": "int64",
        "dia": "int64", "nome_mes": "string", "trimestre": "int64", "ano_mes": "string",
        "dia_semana": "string", "eh_fim_semana": "bool",
    }),
    ("dim_paciente", "dim_paciente.csv", "id_paciente", {
        "id_paciente": "string", "sexo": "string", "faixa_etaria": "string",
    }),
    ("dim_procedimento", "dim_procedimento.csv", "id_procedimento", {
        "id_procedimento": "string", "descricao_procedimento": "string", "especialidade": "string",
        "complexidade": "string", "porte_cirurgico": "string", "tmp_protocolo_previsto": "float64",
    }),
    ("dim_diagnostico", "dim_diagnostico.csv", "cid_10", {
        "cid_10": "string", "descricao_cid": "string", "capitulo_cid": "string", "grau_severidade": "string",
    }),
    ("dim_setor_leito", "dim_setor_leito.csv", "id_leito", {
        "id_leito": "string", "tipo_acomodacao": "string", "setor_hospitalar": "string", "leitos_operacionais": "Int64",
    }),
    ("fato_internacoes", "fato_internacoes.csv", "id_atendimento", {
        "id_atendimento": "string", "id_paciente": "string", "id_procedimento": "string", "cid_10": "string",
        "id_leito": "string", "id_data_admissao": "int64", "id_data_alta": "Int64",
        "dias_permanencia": "Int64", "dias_uti": "Int64", "qtd_diarias": "Int64",
        "custo_hospitalar": "float64", "custo_servicos_profissionais": "float64", "custo_opme": "float64",
        "custo_sadt": "float64", "custo_total": "float64", "receita_faturada": "float64",
        "margem_contribuicao": "float64", "status_desfecho": "string", "indicador_obito": "Int64",
        "readmissao_30d": "boolean",
    }),
]


def read_table(path: Path, types: dict) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo processado não encontrado: {path}")
    actual = set(pd.read_csv(path, sep=";", nrows=0).columns)
    expected = set(types)
    if actual != expected:
        raise ValueError(f"Esquema inesperado em {path.name}: ausentes={sorted(expected - actual)}, extras={sorted(actual - expected)}")
    return pd.read_csv(path, sep=";", dtype=types, usecols=list(types))


def validate_files(data_dir: Path = DATA_DIR) -> bool:
    total = 0
    for table, filename, _primary_key, types in TABLE_CONFIG:
        frame = read_table(data_dir / filename, types)
        total += len(frame)
        print(f"{table:<22} {len(frame):>8,} linhas")
    print(f"Total local: {total:,} linhas prontas para carga.")
    return True


def validated_url():
    value = os.getenv("MYSQL_URL", "").strip()
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        parsed, port = None, None
    if not parsed or parsed.scheme not in {"mysql", "mysql+pymysql"} or not parsed.hostname or not parsed.username or not parsed.password or parsed.path in {"", "/"}:
        raise ValueError("MYSQL_URL precisa ser uma URL MySQL válida.")
    if parsed.username.lower() == "root":
        raise ValueError("Use uma role ETL dedicada; não carregue dados com root.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("A porta em MYSQL_URL é inválida.")
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not local and os.getenv("MYSQL_TLS") != "true":
        raise ValueError("Defina MYSQL_TLS=true para conexões MySQL remotas.")
    return make_url(value).set(drivername="mysql+pymysql")


def upsert_batch(table, connection, keys, rows, primary_key):
    records = []
    for row in rows:
        record = {}
        for key, value in zip(keys, row):
            if pd.isna(value):
                record[key] = None
            elif hasattr(value, "item"):
                record[key] = value.item()
            else:
                record[key] = value
        records.append(record)
    if not records:
        return 0
    statement = mysql_insert(table.table).values(records)
    updates = {
        column.name: statement.inserted[column.name]
        for column in table.table.columns
        if column.name != primary_key
    }
    result = connection.execute(statement.on_duplicate_key_update(**updates))
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(description="Carga do Star Schema hospitalar para MySQL.")
    parser.add_argument("--dry-run", action="store_true", help="Valida apenas os arquivos locais, sem conectar ao banco.")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Diretório dos seis CSVs processados.")
    parser.add_argument("--truncate", action="store_true", help="Apaga os dados antes da carga; use também --confirm-truncate.")
    parser.add_argument("--confirm-truncate", action="store_true", help="Confirma a substituição completa dos dados.")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5000:
        parser.error("--batch-size deve ficar entre 1 e 5000.")
    if args.truncate != args.confirm_truncate:
        parser.error("Use --truncate e --confirm-truncate juntos para confirmar a substituição.")
    try:
        if args.dry_run:
            validate_files(args.data_dir)
            return
        url = validated_url()
        tls_args = {}
        if os.getenv("MYSQL_TLS") == "true":
            ca_file = os.getenv("MYSQL_SSL_CA_FILE")
            tls_args.update(ssl_verify_cert=True, ssl_verify_identity=True)
            if ca_file:
                tls_args["ssl_ca"] = ca_file
        engine = create_engine(url, connect_args=tls_args, pool_pre_ping=True, pool_recycle=300)
        total = 0
        started = time.time()
        with engine.begin() as connection:
            if args.truncate:
                for table, _filename, _primary_key, _types in reversed(TABLE_CONFIG):
                    connection.execute(text(f"DELETE FROM `{table}`"))
            for table, filename, primary_key, types in TABLE_CONFIG:
                frame = read_table(args.data_dir / filename, types)
                frame.to_sql(
                    name=table,
                    con=connection,
                    if_exists="append",
                    index=False,
                    chunksize=args.batch_size,
                    method=lambda target, conn, keys, rows, pk=primary_key: upsert_batch(target, conn, keys, rows, pk),
                )
                total += len(frame)
                print(f"{table}: {len(frame):,} linhas inseridas/atualizadas")
        engine.dispose()
        print(f"Carga MySQL concluída: {total:,} linhas em {time.time() - started:.1f}s.")
    except Exception as error:
        print(f"Falha na carga ({type(error).__name__}). Confira arquivos, conexão, TLS e permissões.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

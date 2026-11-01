"""Carga segura dos agregados sintéticos para as views consumidas pela Vercel."""

from __future__ import annotations

import argparse
import calendar
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "benchmark"
RUNTIME_CONFIG = PROJECT_ROOT / ".env.mysql-runtime.json"
WEEKDAYS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
COMPONENTS = [
    "custo_hospitalar",
    "custo_servicos_profissionais",
    "custo_opme",
    "custo_sadt",
]
TABLES = [
    "benchmark_resumo_mensal",
    "benchmark_ocupacao_mensal",
    "benchmark_custos_procedimento",
    "benchmark_chegadas_hora",
    "benchmark_metadata",
]


def read_source(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    database = data_dir / "hospital_analytics.duckdb"
    if not database.is_file():
        raise FileNotFoundError(
            f"Benchmark DuckDB não encontrado: {database}. Gere-o com src/generate_benchmark_dataset.py."
        )

    connection = duckdb.connect(str(database), read_only=True)
    try:
        facts = connection.execute(
            """
            SELECT
                f.*,
                p.descricao_procedimento,
                p.especialidade,
                s.setor_hospitalar,
                s.leitos_operacionais,
                pos.setor_hospitalar AS setor_pos_uti
            FROM fato_internacoes AS f
            JOIN dim_procedimento AS p USING (id_procedimento)
            JOIN dim_setor_leito AS s USING (id_leito)
            JOIN dim_setor_leito AS pos ON f.id_leito_pos_uti = pos.id_leito
            """
        ).df()
        sectors = connection.execute(
            "SELECT id_leito, setor_hospitalar, leitos_operacionais FROM dim_setor_leito"
        ).df()
        metadata_rows = connection.execute(
            "SELECT num_admissoes, seed, ano_chegada, leitos_operacionais FROM benchmark_metadata LIMIT 1"
        ).fetchone()
    finally:
        connection.close()

    if not metadata_rows or len(facts) != int(metadata_rows[0]):
        raise ValueError("Os metadados do benchmark não correspondem à tabela de internações.")
    metadata = {
        "num_admissoes": int(metadata_rows[0]),
        "seed": int(metadata_rows[1]),
        "ano_chegada": int(metadata_rows[2]),
        "leitos_operacionais": int(metadata_rows[3]),
    }
    facts["data_hora_chegada"] = pd.to_datetime(facts["data_hora_chegada"])
    facts["data_hora_internacao"] = pd.to_datetime(facts["data_hora_internacao"])
    facts["ano_mes"] = facts["data_hora_chegada"].dt.strftime("%Y-%m")
    return facts, sectors, metadata


def build_summary(facts: pd.DataFrame) -> pd.DataFrame:
    summary = (
        facts.groupby(["ano_mes", "especialidade", "id_leito", "setor_hospitalar", "leitos_operacionais"], as_index=False)
        .agg(
            volume_internacoes=("id_atendimento", "count"),
            espera_media_minutos=("tempo_espera_minutos", "mean"),
            **{column: (column, "sum") for column in COMPONENTS},
            custo_total=("custo_total", "sum"),
        )
        .sort_values(["ano_mes", "especialidade", "id_leito"])
    )
    summary["espera_media_minutos"] = summary["espera_media_minutos"].round(2)
    return summary


def build_costs(facts: pd.DataFrame) -> pd.DataFrame:
    return (
        facts.groupby(
            ["ano_mes", "especialidade", "id_leito", "setor_hospitalar", "id_procedimento", "descricao_procedimento"],
            as_index=False,
        )
        .agg(**{column: (column, "sum") for column in COMPONENTS}, custo_total=("custo_total", "sum"))
        .sort_values(["ano_mes", "especialidade", "id_leito", "id_procedimento"])
    )


def build_occupancy(facts: pd.DataFrame, sectors: pd.DataFrame, year: int) -> pd.DataFrame:
    capacities = sectors.set_index("setor_hospitalar")["leitos_operacionais"].to_dict()
    patient_days: Counter[tuple[str, str]] = Counter()

    for row in facts.itertuples(index=False):
        admission_day = pd.Timestamp(row.data_hora_internacao).date()
        total_days = int(row.dias_permanencia)
        if row.id_leito == "LEITO_UTI_01":
            icu_days = min(total_days, max(0, int(row.dias_uti)))
            stays = [
                (row.setor_hospitalar, admission_day, icu_days),
                (row.setor_pos_uti, admission_day + timedelta(days=icu_days), total_days - icu_days),
            ]
        else:
            stays = [(row.setor_hospitalar, admission_day, total_days)]

        for sector, start_day, stay_days in stays:
            for offset in range(stay_days):
                occupied_day = start_day + timedelta(days=offset)
                if occupied_day.year == year:
                    patient_days[(occupied_day.strftime("%Y-%m"), sector)] += 1

    rows = []
    for month in range(1, 13):
        month_key = f"{year}-{month:02d}"
        days_in_month = calendar.monthrange(year, month)[1]
        for sector, capacity in capacities.items():
            occupied = patient_days[(month_key, sector)]
            available = int(capacity) * days_in_month
            rows.append({
                "ano_mes": month_key,
                "id_leito": sectors.loc[sectors["setor_hospitalar"] == sector, "id_leito"].iloc[0],
                "setor_hospitalar": sector,
                "leitos_operacionais": int(capacity),
                "dias_paciente": occupied,
                "leitos_dia_disponiveis": available,
                "ocupacao_pct": round(occupied * 100 / available, 2) if available else 0,
            })
    return pd.DataFrame(rows)


def build_arrivals(facts: pd.DataFrame) -> pd.DataFrame:
    arrivals = facts.assign(
        dia_semana=facts["data_hora_chegada"].dt.dayofweek,
        hora=facts["data_hora_chegada"].dt.hour,
    )
    counts = arrivals.groupby(["dia_semana", "hora"]).size()
    return pd.DataFrame([
        {
            "dia_semana": day,
            "nome_dia": WEEKDAYS_PT[day],
            "hora": hour,
            "volume_chegadas": int(counts.get((day, hour), 0)),
        }
        for day in range(7)
        for hour in range(24)
    ])


def build_aggregates(data_dir: Path) -> dict[str, pd.DataFrame]:
    facts, sectors, metadata = read_source(data_dir)
    metadata_frame = pd.DataFrame([{
        "id": 1,
        "num_admissoes": metadata["num_admissoes"],
        "seed": metadata["seed"],
        "ano_chegada": metadata["ano_chegada"],
        "leitos_operacionais": metadata["leitos_operacionais"],
    }])
    return {
        "benchmark_resumo_mensal": build_summary(facts),
        "benchmark_ocupacao_mensal": build_occupancy(facts, sectors, metadata["ano_chegada"]),
        "benchmark_custos_procedimento": build_costs(facts),
        "benchmark_chegadas_hora": build_arrivals(facts),
        "benchmark_metadata": metadata_frame,
    }


def create_runtime_engine():
    if not RUNTIME_CONFIG.is_file():
        raise FileNotFoundError(".env.mysql-runtime.json não foi encontrado; configure a conexão MySQL local.")
    runtime = json.loads(RUNTIME_CONFIG.read_text())
    loader_url = make_url(runtime["urls"]["analytics_loader"])
    if loader_url.username != "analytics_loader" or not loader_url.password or not loader_url.host:
        raise ValueError("A URL local deve usar a conta analytics_loader.")
    if loader_url.host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("A conexão de produção do benchmark deve usar o endpoint remoto com TLS.")
    ca = runtime.get("ca", "")
    if "BEGIN CERTIFICATE" not in ca:
        raise ValueError("A CA TLS da conexão MySQL não foi encontrada no runtime local.")

    ca_file = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", encoding="utf-8", delete=False)
    try:
        os.chmod(ca_file.name, 0o600)
        ca_file.write(ca)
        ca_file.close()
        engine = create_engine(
            loader_url.set(drivername="mysql+pymysql"),
            connect_args={
                "ssl_verify_cert": True,
                "ssl_verify_identity": True,
                "ssl_ca": ca_file.name,
            },
            pool_pre_ping=True,
            pool_recycle=300,
        )
        return engine, Path(ca_file.name)
    except Exception:
        Path(ca_file.name).unlink(missing_ok=True)
        raise


def load_snapshot(aggregates: dict[str, pd.DataFrame]) -> None:
    engine, ca_path = create_runtime_engine()
    try:
        with engine.begin() as connection:
            for table in TABLES:
                connection.execute(text(f"DELETE FROM `{table}`"))
            for table in TABLES:
                frame = aggregates[table]
                frame.to_sql(
                    name=table,
                    con=connection,
                    if_exists="append",
                    index=False,
                    chunksize=500,
                    method="multi",
                )
        row_counts = {table: len(aggregates[table]) for table in TABLES}
        print(json.dumps({"loaded": True, "tables": row_counts, "source": "benchmark-synthetic"}, ensure_ascii=False))
    finally:
        engine.dispose()
        ca_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publica agregados do benchmark sintético nas views da Vercel.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Calcula os agregados sem conectar ao MySQL.")
    args = parser.parse_args()
    try:
        aggregates = build_aggregates(args.data_dir)
        counts = {table: len(frame) for table, frame in aggregates.items()}
        if args.dry_run:
            metadata = aggregates["benchmark_metadata"].iloc[0]
            print(json.dumps({"ready": True, "metadata": {
                "num_admissoes": int(metadata["num_admissoes"]),
                "seed": int(metadata["seed"]),
                "ano_chegada": int(metadata["ano_chegada"]),
            }, "aggregate_rows": counts}, ensure_ascii=False))
            return
        load_snapshot(aggregates)
    except Exception as error:
        print(f"Falha na carga sintética ({type(error).__name__}). Confira o benchmark, a migração e a conexão TLS.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Carga agregada de SIH/SUS, CNES e fila SISREG pública de Alagoas para o dashboard."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sih_data import consolidate_aih_versions
from public_sus_quality import validate_public_aggregates


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SIH_RAW = PROJECT_ROOT / "data" / "raw" / "sih_al_2025_01-12_raw.parquet"
DEFAULT_CACHE = PROJECT_ROOT / "data" / "public_sus"
RUNTIME_CONFIG = PROJECT_ROOT / ".env.mysql-runtime.json"
YEAR = 2025
UF = "AL"
SISREG_SNAPSHOT_DATE = date(2025, 8, 10)
MINIMUM_PUBLIC_GROUP = 30
CNES_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/json/Leitos_json_2025.zip"
SISREG_URL = "https://cidadao.saude.al.gov.br/wp-content/uploads/2025/09/Fila-de-Espera-2022-2025-AGOSTO.pdf"
SIH_SOURCE_URL = "https://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados/"
TABLES = [
    "sih_publico_aih_mensal",
    "sih_publico_aih_procedimento",
    "cnes_leitos_publicos_mensal",
    "sih_ocupacao_estimada_mensal",
    "sisreg_fila_publica_procedimento",
]
DATE_TOKEN = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
REQUEST_TOKEN = re.compile(r"^\d+\*+$")


def download_if_missing(path: Path, url: str) -> Path:
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=(20, 300)) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output.write(chunk)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def read_cnes_beds(path: Path) -> pd.DataFrame:
    if not zipfile.is_zipfile(path):
        raise ValueError("O arquivo CNES não é um ZIP válido.")
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".json")]
        if len(members) != 1:
            raise ValueError("O ZIP CNES não contém um único arquivo JSON esperado.")
        with archive.open(members[0]) as source:
            frame = pd.read_json(source)

    required = {"COMP", "UF", "CNES", "DS_TIPO_UNIDADE", "LEITOS_SUS", "UTI_TOTAL_SUS"}
    if not required.issubset(frame.columns):
        raise ValueError("O arquivo CNES não tem as colunas públicas esperadas.")
    frame = frame.loc[frame["UF"].astype(str).str.upper().eq(UF)].copy()
    frame["COMP"] = frame["COMP"].astype(str).str.zfill(6)
    frame = frame.loc[frame["COMP"].str.startswith(str(YEAR))]
    if frame.empty:
        raise ValueError(f"O arquivo CNES não tem competências de {YEAR} para {UF}.")

    for column in ("LEITOS_SUS", "UTI_TOTAL_SUS"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0).astype("int64")
    frame["ano_mes"] = frame["COMP"].str.slice(0, 4) + "-" + frame["COMP"].str.slice(4, 6)
    hospital_type = frame["DS_TIPO_UNIDADE"].astype(str).str.contains(
        r"HOSPITAL|PRONTO\s*SOCORRO", case=False, regex=True, na=False
    )
    monthly = frame.groupby("ano_mes", as_index=False).agg(
        leitos_gerais_sus=("LEITOS_SUS", "sum"),
        leitos_uti_sus=("UTI_TOTAL_SUS", "sum"),
    )
    hospital_counts = (
        frame.loc[hospital_type].groupby("ano_mes")["CNES"].nunique()
        .rename("estabelecimentos_hospitalares")
    )
    monthly = monthly.merge(hospital_counts, on="ano_mes", how="left")
    monthly["estabelecimentos_hospitalares"] = monthly["estabelecimentos_hospitalares"].fillna(0).astype("int64")
    monthly["total_leitos_sus"] = monthly["leitos_gerais_sus"] + monthly["leitos_uti_sus"]
    monthly["uf"] = UF
    monthly = monthly[[
        "ano_mes", "uf", "estabelecimentos_hospitalares", "leitos_gerais_sus",
        "leitos_uti_sus", "total_leitos_sus",
    ]].sort_values("ano_mes").reset_index(drop=True)
    monthly.attrs["source_records"] = len(frame)
    expected_months = {f"{YEAR}-{month:02d}" for month in range(1, 13)}
    if set(monthly["ano_mes"]) != expected_months or monthly["total_leitos_sus"].le(0).any():
        raise ValueError("A série CNES precisa conter 12 competências válidas com leitos SUS.")
    if frame.duplicated(["COMP", "CNES"]).any():
        raise ValueError("O arquivo CNES contém duplicidade de estabelecimento e competência.")
    return monthly


def read_sih_records(path: Path) -> tuple[pd.DataFrame, int, int]:
    if not path.is_file():
        raise FileNotFoundError(f"Parquet bruto SIH/SUS não encontrado: {path}")
    columns = [
        "N_AIH", "ANO_CMPT", "MES_CMPT", "IDENT", "SEQ_AIH5", "SEQUENCIA",
        "DT_INTER", "DT_SAIDA", "DIAS_PERM", "QT_DIARIAS", "PROC_REA",
        "DIAG_PRINC", "VAL_TOT", "SEXO", "IDADE", "COD_IDADE", "MORTE", "UTI_MES_TO",
    ]
    records = pd.read_parquet(path, columns=columns)
    source_records = len(records)
    records, consolidated_rows = consolidate_aih_versions(records)
    date_values = records["DT_INTER"].astype("string").str.strip().str.replace(r"\.0+$", "", regex=True)
    records["data_admissao"] = pd.to_datetime(date_values, format="%Y%m%d", errors="coerce")
    records["dias_permanencia"] = pd.to_numeric(records["DIAS_PERM"], errors="coerce")
    records["dias_permanencia"] = records["dias_permanencia"].where(
        records["dias_permanencia"].ge(0) & records["dias_permanencia"].mod(1).eq(0)
    )
    records["valor_aih"] = pd.to_numeric(records["VAL_TOT"], errors="coerce")
    procedure = records["PROC_REA"].astype("string").str.strip().str.upper().str.replace(r"\.0+$", "", regex=True)
    numeric_procedure = procedure.str.fullmatch(r"\d+", na=False)
    procedure.loc[numeric_procedure] = procedure.loc[numeric_procedure].str.zfill(10)
    records["id_procedimento"] = procedure.mask(procedure.isin(["", "NAN", "NONE", "<NA>"])).fillna("SEM_INFO")
    records = records.dropna(subset=["data_admissao"]).copy()
    if records.empty:
        raise ValueError("Nenhuma AIH contém data de admissão válida.")
    return records, consolidated_rows, source_records


def summarize_sih_group(group: pd.DataFrame, ano_mes: str, procedure: str | None = None) -> dict:
    stay = group["dias_permanencia"]
    value = group["valor_aih"]
    all_stays_known = stay.notna().all()
    all_values_known = value.notna().all()
    row = {
        "ano_mes": ano_mes,
        "volume_aih": int(len(group)),
        "dias_permanencia": int(stay.sum()) if all_stays_known else None,
        "permanencia_media_dias": round(float(stay.mean()), 1) if all_stays_known and len(group) else None,
        "valor_aih_total": round(float(value.sum()), 2) if all_values_known else None,
        "aihs_com_valor": int(value.notna().sum()),
    }
    if procedure is not None:
        row["id_procedimento"] = procedure
    return row


def aggregate_sih_2025(records: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cohort = records.loc[
        records["data_admissao"].dt.year.eq(YEAR)
        & records["data_admissao"].dt.date.between(date(YEAR, 1, 1), date(YEAR, 12, 31))
    ].copy()
    if cohort.empty:
        raise ValueError(f"Não há AIHs com admissão em {YEAR}.")
    cohort["ano_mes"] = cohort["data_admissao"].dt.strftime("%Y-%m")
    monthly_groups = {key: group for key, group in cohort.groupby("ano_mes", sort=True)}
    monthly_rows = []
    for month in range(1, 13):
        key = f"{YEAR}-{month:02d}"
        group = monthly_groups.get(key)
        if group is None:
            monthly_rows.append({
                "ano_mes": key, "volume_aih": 0, "dias_permanencia": 0,
                "permanencia_media_dias": None, "valor_aih_total": 0.0, "aihs_com_valor": 0,
            })
        else:
            monthly_rows.append(summarize_sih_group(group, key))
    monthly = pd.DataFrame(monthly_rows)

    procedure_rows = []
    for (month, procedure), group in cohort.groupby(["ano_mes", "id_procedimento"], sort=True):
        procedure_rows.append(summarize_sih_group(group, month, str(procedure)))
    procedure_monthly = pd.DataFrame(procedure_rows)

    annual_rows = []
    for procedure, group in cohort.groupby("id_procedimento", sort=True):
        annual_rows.append(summarize_sih_group(group, str(YEAR), str(procedure)))
    procedure_annual = pd.DataFrame(annual_rows)
    procedures = pd.concat([procedure_monthly, procedure_annual], ignore_index=True)
    if procedures.duplicated(["ano_mes", "id_procedimento"]).any():
        raise ValueError("O agregado SIH contém códigos e períodos duplicados.")
    return monthly, procedures, cohort


def read_sih_stays(records: pd.DataFrame) -> pd.DataFrame:
    year_start, year_end = date(YEAR, 1, 1), date(YEAR, 12, 31)
    facts = records.loc[records["dias_permanencia"].gt(0), ["data_admissao", "dias_permanencia"]].copy()
    facts["data_admissao_date"] = facts["data_admissao"].dt.date
    facts["data_alta_estimada"] = [
        admission + timedelta(days=int(days) - 1)
        for admission, days in zip(facts["data_admissao_date"], facts["dias_permanencia"])
    ]
    facts = facts.loc[
        facts["data_admissao_date"].le(year_end)
        & facts["data_alta_estimada"].ge(year_start)
    ]
    if facts.empty:
        raise ValueError(f"Não há AIHs com permanência sobreposta a {YEAR}.")
    return facts[["data_admissao_date", "dias_permanencia"]].rename(columns={"data_admissao_date": "data_admissao"})


def build_occupancy(facts: pd.DataFrame, capacity: pd.DataFrame) -> pd.DataFrame:
    patient_days: defaultdict[str, int] = defaultdict(int)
    year_start, year_end = date(YEAR, 1, 1), date(YEAR, 12, 31)
    for row in facts.itertuples(index=False):
        start = max(row.data_admissao, year_start)
        end = min(row.data_admissao + timedelta(days=int(row.dias_permanencia) - 1), year_end)
        while start <= end:
            month_end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
            covered_end = min(end, month_end)
            patient_days[start.strftime("%Y-%m")] += (covered_end - start).days + 1
            start = covered_end + timedelta(days=1)

    rows = []
    for capacity_row in capacity.itertuples(index=False):
        month_days = calendar.monthrange(YEAR, int(capacity_row.ano_mes[-2:]))[1]
        available_bed_days = int(capacity_row.total_leitos_sus) * month_days
        occupied_days = patient_days[capacity_row.ano_mes]
        rows.append({
            "ano_mes": capacity_row.ano_mes,
            "dias_paciente_sih": occupied_days,
            "leitos_sus_cnes": int(capacity_row.total_leitos_sus),
            "leitos_dia_disponiveis": available_bed_days,
            "ocupacao_estimada_pct": round(occupied_days * 100 / available_bed_days, 2),
        })
    return pd.DataFrame(rows)


def read_sisreg_queue(path: Path) -> pd.DataFrame:
    document = pymupdf.open(path)
    pending_by_procedure: defaultdict[str, list[int]] = defaultdict(list)
    malformed_rows = 0
    try:
        for page in document:
            current: dict[str, object] | None = None

            def finish_row() -> None:
                nonlocal malformed_rows
                if current is None:
                    return
                procedure = " ".join(current["procedure_tokens"]).strip()  # type: ignore[arg-type]
                requested_at = current["requested_at"]
                if not procedure or not isinstance(requested_at, date):
                    malformed_rows += 1
                    return
                if requested_at > SISREG_SNAPSHOT_DATE:
                    malformed_rows += 1
                    return
                pending_by_procedure[procedure].append((SISREG_SNAPSHOT_DATE - requested_at).days)

            for word in page.get_text("words", sort=True):
                x0, token = float(word[0]), str(word[4]).strip()
                # O identificador da solicitação é ignorado e nunca é armazenado.
                if x0 < 75 and REQUEST_TOKEN.fullmatch(token):
                    finish_row()
                    current = {"procedure_tokens": [], "requested_at": None}
                    continue
                if current is None:
                    continue
                if 75 <= x0 < 258 and token not in {"Solicitação", "Procedimento", "/", "Devolvida", "Regulador"}:
                    current["procedure_tokens"].append(token)  # type: ignore[union-attr]
                elif 360 <= x0 < 405 and DATE_TOKEN.fullmatch(token):
                    current["requested_at"] = datetime.strptime(token, "%d/%m/%Y").date()
            finish_row()
    finally:
        document.close()

    if malformed_rows:
        raise ValueError(f"O PDF SISREG tem {malformed_rows} linhas não interpretadas; a carga foi interrompida.")
    rows = []
    suppressed_groups = 0
    for procedure, ages in pending_by_procedure.items():
        if len(ages) < MINIMUM_PUBLIC_GROUP:
            suppressed_groups += 1
            continue
        if len(procedure) > 255:
            raise ValueError("Um procedimento do SISREG excede o tamanho esperado no esquema.")
        rows.append({
            "data_extracao": SISREG_SNAPSHOT_DATE,
            "procedimento": procedure,
            "solicitacoes_pendentes": len(ages),
            "espera_media_dias": int(round(float(np.mean(ages)))),
            "espera_mediana_dias": int(round(float(np.median(ages)))),
            "espera_p90_dias": int(round(float(np.percentile(ages, 90)))),
            "espera_max_dias": int(max(ages)),
        })
    if not rows:
        raise ValueError("Nenhum grupo SISREG passou o limite de supressão.")
    result = pd.DataFrame(rows).sort_values(
        ["espera_p90_dias", "solicitacoes_pendentes"], ascending=[False, False]
    ).reset_index(drop=True)
    result.attrs["suppressed_groups"] = suppressed_groups
    result.attrs["pending_requests_analyzed"] = sum(map(len, pending_by_procedure.values()))
    all_ages = [age for ages in pending_by_procedure.values() for age in ages]
    if all_ages:
        result.attrs["coverage_start"] = SISREG_SNAPSHOT_DATE - timedelta(days=max(all_ages))
        result.attrs["coverage_end"] = SISREG_SNAPSHOT_DATE - timedelta(days=min(all_ages))
    return result


def create_runtime_engine():
    if not RUNTIME_CONFIG.is_file():
        raise FileNotFoundError(".env.mysql-runtime.json não foi encontrado.")
    runtime = json.loads(RUNTIME_CONFIG.read_text())
    loader_url = make_url(runtime["urls"]["analytics_loader"])
    if loader_url.username != "analytics_loader" or not loader_url.password or not loader_url.host:
        raise ValueError("A URL precisa usar a conta local analytics_loader.")
    if loader_url.host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("A conexão MySQL de carga precisa usar o endpoint remoto com TLS.")
    ca = runtime.get("ca", "")
    if "BEGIN CERTIFICATE" not in ca:
        raise ValueError("A CA TLS não foi encontrada na configuração local.")

    ca_file = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", encoding="utf-8", delete=False)
    try:
        os.chmod(ca_file.name, 0o600)
        ca_file.write(ca)
        ca_file.close()
        engine = create_engine(
            loader_url.set(drivername="mysql+pymysql"),
            connect_args={"ssl_verify_cert": True, "ssl_verify_identity": True, "ssl_ca": ca_file.name},
            pool_pre_ping=True,
            pool_recycle=300,
        )
        return engine, Path(ca_file.name)
    except Exception:
        Path(ca_file.name).unlink(missing_ok=True)
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest_rows(
    *,
    sih_path: Path,
    sih_source_records: int,
    records: pd.DataFrame,
    cohort: pd.DataFrame,
    aggregates: dict[str, pd.DataFrame],
    cnes_path: Path | None = None,
    capacity: pd.DataFrame | None = None,
    sisreg_path: Path | None = None,
    waiting: pd.DataFrame | None = None,
) -> list[dict[str, object]]:
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    manifest = [{
        "source_key": "sih_sus",
        "source_label": "SIH/SUS",
        "source_url": SIH_SOURCE_URL,
        "data_through": None,
        "coverage_start": cohort["data_admissao"].min().date(),
        "coverage_end": cohort["data_admissao"].max().date(),
        "source_record_count": int(sih_source_records),
        "aggregate_row_count": int(
            len(aggregates["sih_publico_aih_mensal"])
            + len(aggregates["sih_publico_aih_procedimento"])
        ),
        "source_sha256": sha256_file(sih_path),
        "loaded_at_utc": loaded_at,
    }]

    if {"ANO_CMPT", "MES_CMPT"}.issubset(records.columns):
        processing_year = pd.to_numeric(records["ANO_CMPT"], errors="coerce")
        processing_month = pd.to_numeric(records["MES_CMPT"], errors="coerce")
        valid = processing_year.notna() & processing_month.between(1, 12)
        if valid.any():
            latest = max(
                (int(year), int(month))
                for year, month in zip(processing_year[valid], processing_month[valid])
            )
            manifest[0]["data_through"] = date(
                latest[0], latest[1], calendar.monthrange(*latest)[1]
            )

    if cnes_path is not None and capacity is not None:
        manifest.append({
            "source_key": "cnes",
            "source_label": "CNES · leitos SUS",
            "source_url": CNES_URL,
            "data_through": date(YEAR, 12, 31),
            "coverage_start": date(YEAR, 1, 1),
            "coverage_end": date(YEAR, 12, 31),
            "source_record_count": int(capacity.attrs.get("source_records", 0)),
            "aggregate_row_count": int(len(capacity)),
            "source_sha256": sha256_file(cnes_path),
            "loaded_at_utc": loaded_at,
        })

    if sisreg_path is not None and waiting is not None:
        manifest.append({
            "source_key": "sisreg",
            "source_label": "SISREG · SESAU/AL",
            "source_url": SISREG_URL,
            "data_through": SISREG_SNAPSHOT_DATE,
            "coverage_start": waiting.attrs.get("coverage_start"),
            "coverage_end": waiting.attrs.get("coverage_end"),
            "source_record_count": int(waiting.attrs.get("pending_requests_analyzed", 0)),
            "aggregate_row_count": int(len(waiting)),
            "source_sha256": sha256_file(sisreg_path),
            "loaded_at_utc": loaded_at,
        })
    return manifest


def load_snapshot(
    aggregates: dict[str, pd.DataFrame], manifest_rows: list[dict[str, object]]
) -> None:
    engine, ca_path = create_runtime_engine()
    try:
        with engine.begin() as connection:
            for table in aggregates:
                connection.execute(text(f"DELETE FROM `{table}`"))
            for table in aggregates:
                aggregates[table].to_sql(
                    name=table, con=connection, if_exists="append", index=False,
                    chunksize=500, method="multi",
                )
            connection.execute(
                text("""INSERT INTO public_sus_dataset_manifest (
                    source_key, source_label, source_url, data_through,
                    coverage_start, coverage_end, source_record_count,
                    aggregate_row_count, source_sha256, loaded_at_utc
                ) VALUES (
                    :source_key, :source_label, :source_url, :data_through,
                    :coverage_start, :coverage_end, :source_record_count,
                    :aggregate_row_count, :source_sha256, :loaded_at_utc
                ) ON DUPLICATE KEY UPDATE
                    source_label = VALUES(source_label), source_url = VALUES(source_url),
                    data_through = VALUES(data_through), coverage_start = VALUES(coverage_start),
                    coverage_end = VALUES(coverage_end), source_record_count = VALUES(source_record_count),
                    aggregate_row_count = VALUES(aggregate_row_count), source_sha256 = VALUES(source_sha256),
                    loaded_at_utc = VALUES(loaded_at_utc)"""),
                manifest_rows,
            )
        print(json.dumps({
            "loaded": True,
            "tables": {table: len(frame) for table, frame in aggregates.items()},
            "manifest_sources": [row["source_key"] for row in manifest_rows],
            "source": " + ".join(
                source for table, source in [
                    ("sih_publico_aih_mensal", "SIH/SUS"),
                    ("cnes_leitos_publicos_mensal", "CNES"),
                    ("sisreg_fila_publica_procedimento", "SISREG Alagoas"),
                ] if table in aggregates
            ),
            "sisreg_extraction_date": SISREG_SNAPSHOT_DATE.isoformat() if "sisreg_fila_publica_procedimento" in aggregates else None,
            "sisreg_group_suppression_minimum": MINIMUM_PUBLIC_GROUP if "sisreg_fila_publica_procedimento" in aggregates else None,
        }, ensure_ascii=False))
    finally:
        engine.dispose()
        ca_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Carrega agregados públicos do SUS para as views da Vercel.")
    parser.add_argument("--sih-raw", type=Path, default=DEFAULT_SIH_RAW, help="Parquet bruto SIH/SUS com competência e tipo de AIH preservados.")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--cnes-zip", type=Path, help="Arquivo CNES local; sem ele, usa o cache ou baixa a fonte oficial.")
    parser.add_argument("--sisreg-pdf", type=Path, help="PDF SISREG local; sem ele, usa o cache ou baixa a fonte estadual.")
    parser.add_argument("--sih-only", action="store_true", help="Atualiza somente agregados SIH e a ocupação calculada com CNES já carregado.")
    parser.add_argument("--dry-run", action="store_true", help="Calcula e valida os agregados sem conectar ao MySQL.")
    args = parser.parse_args()

    try:
        records, consolidated_rows, sih_source_records = read_sih_records(args.sih_raw)
        sih_monthly, sih_procedures, cohort = aggregate_sih_2025(records)
        stays = read_sih_stays(records)
        sih_aggregates = {
            "sih_publico_aih_mensal": sih_monthly,
            "sih_publico_aih_procedimento": sih_procedures,
        }

        if args.sih_only:
            aggregates = sih_aggregates
            waiting = None
            cnes_path = None
            sisreg_path = None
            capacity = None
            if not args.dry_run:
                engine, ca_path = create_runtime_engine()
                try:
                    with engine.connect() as connection:
                        capacity = pd.read_sql(
                            text("""SELECT ano_mes, total_leitos_sus
                                    FROM cnes_leitos_publicos_mensal
                                    WHERE uf = :uf AND ano_mes LIKE :year_prefix
                                    ORDER BY ano_mes"""),
                            connection,
                            params={"uf": UF, "year_prefix": f"{YEAR}-%"},
                        )
                    expected = {f"{YEAR}-{month:02d}" for month in range(1, 13)}
                    if set(capacity["ano_mes"]) != expected or capacity["total_leitos_sus"].le(0).any():
                        raise ValueError("Carregue primeiro as 12 competências CNES de 2025 antes do modo --sih-only.")
                    aggregates["sih_ocupacao_estimada_mensal"] = build_occupancy(stays, capacity)
                finally:
                    engine.dispose()
                    ca_path.unlink(missing_ok=True)
        else:
            cnes_path = args.cnes_zip or args.cache_dir / "Leitos_json_2025.zip"
            sisreg_path = args.sisreg_pdf or args.cache_dir / "Fila-de-Espera-Alagoas-2025-08.pdf"
            download_if_missing(cnes_path, CNES_URL)
            download_if_missing(sisreg_path, SISREG_URL)
            capacity = read_cnes_beds(cnes_path)
            waiting = read_sisreg_queue(sisreg_path)
            aggregates = {
                **sih_aggregates,
                "sih_ocupacao_estimada_mensal": build_occupancy(stays, capacity),
                "cnes_leitos_publicos_mensal": capacity,
                "sisreg_fila_publica_procedimento": waiting,
            }
        counts = {table: len(frame) for table, frame in aggregates.items()}
        quality_report = validate_public_aggregates(
            aggregates, require_complementary=not args.sih_only
        )
        if not quality_report["passed"]:
            print(json.dumps({
                "ready": False,
                "year": YEAR,
                "uf": UF,
                "aggregate_rows": counts,
                "quality": quality_report,
                "occupancy_checked": "sih_ocupacao_estimada_mensal" in aggregates,
            }, ensure_ascii=False))
            sys.exit(1)
        manifest_rows = build_manifest_rows(
            sih_path=args.sih_raw,
            sih_source_records=sih_source_records,
            records=records,
            cohort=cohort,
            aggregates=aggregates,
            cnes_path=cnes_path,
            capacity=capacity,
            sisreg_path=sisreg_path,
            waiting=waiting,
        )
        if args.dry_run:
            print(json.dumps({
                "ready": True,
                "year": YEAR,
                "uf": UF,
                "aggregate_rows": counts,
                "occupancy_checked": "sih_ocupacao_estimada_mensal" in aggregates,
                "aih_rows_consolidated": consolidated_rows,
                "aih_records_in_admission_cohort": len(cohort),
                "sih_stays_used_for_occupancy": len(stays),
                "sih_duplicate_rows_consolidated": consolidated_rows,
                "sisreg_snapshot_date": SISREG_SNAPSHOT_DATE.isoformat() if waiting is not None else None,
                "sisreg_pending_requests_analyzed": int(waiting.attrs["pending_requests_analyzed"]) if waiting is not None else None,
                "sisreg_groups_suppressed": int(waiting.attrs["suppressed_groups"]) if waiting is not None else None,
                "sisreg_minimum_group_size": MINIMUM_PUBLIC_GROUP if waiting is not None else None,
                "quality": quality_report,
                "manifest": [
                    {key: value for key, value in row.items() if key != "source_sha256"}
                    for row in manifest_rows
                ],
            }, ensure_ascii=False))
            return
        load_snapshot(aggregates, manifest_rows)
    except Exception as error:
        print(
            f"Falha na integração SUS ({type(error).__name__}). Confira fontes, migração e conexão TLS.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

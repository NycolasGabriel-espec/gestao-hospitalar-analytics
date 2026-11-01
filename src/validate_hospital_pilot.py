"""Preflight CSVs for the isolated hospital pilot; rejects columns outside the contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


CONTRACTS = {
    "bed_census": {
        "columns": [
            "hospital_id", "observation_date", "shift_code", "sector_code", "bed_type",
            "operational_beds", "staffed_beds", "occupied_beds", "blocked_beds",
        ],
        "key": ["hospital_id", "observation_date", "shift_code", "sector_code", "bed_type"],
        "dates": ["observation_date"],
        "integers": ["operational_beds", "staffed_beds", "occupied_beds", "blocked_beds"],
        "decimals": [],
    },
    "admissions_monthly": {
        "columns": [
            "hospital_id", "ano_mes", "especialidade", "id_procedimento",
            "volume_admissoes", "volume_altas", "dias_paciente",
        ],
        "key": ["hospital_id", "ano_mes", "especialidade", "id_procedimento"],
        "dates": ["ano_mes"],
        "integers": ["volume_admissoes", "volume_altas", "dias_paciente"],
        "decimals": [],
    },
    "financial_monthly": {
        "columns": [
            "hospital_id", "ano_mes", "centro_custo", "id_procedimento",
            "receita_recebida", "custo_hospitalar", "custo_servicos_profissionais",
            "custo_opme", "custo_sadt",
        ],
        "key": ["hospital_id", "ano_mes", "centro_custo", "id_procedimento"],
        "dates": ["ano_mes"],
        "integers": [],
        "decimals": [
            "receita_recebida", "custo_hospitalar", "custo_servicos_profissionais",
            "custo_opme", "custo_sadt",
        ],
    },
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
PROCEDURE_PATTERN = re.compile(r"^(?:\d{10}|SEM_INFO)$")
CODE_COLUMNS = {"shift_code", "sector_code", "bed_type", "especialidade", "centro_custo"}
DECIMAL_PATTERN = re.compile(r"^-?\d+(?:\.\d{1,2})?$")
DECIMAL_MAX = Decimal("99999999999999.99")


def validate_csv(contract_name: str, path: Path) -> dict[str, object]:
    contract = CONTRACTS[contract_name]
    errors: list[str] = []
    warnings: list[str] = []
    row_count = 0
    seen_keys: set[tuple[str, ...]] = set()

    try:
        source = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as error:
        return {"file": contract_name, "rows": 0, "errors": [f"unreadable_file:{type(error).__name__}"]}

    with source:
        reader = csv.DictReader(source)
        header = reader.fieldnames or []
        if len(header) != len(set(header)):
            errors.append("duplicate_header_column")
        if header != contract["columns"]:
            errors.append("header_must_match_contract_exactly")
            return {"file": contract_name, "rows": 0, "errors": errors}

        for row_number, row in enumerate(reader, start=2):
            row_count += 1
            if None in row:
                errors.append(f"extra_csv_fields:row_{row_number}")
                continue
            if any(value is None or not value.strip() for value in row.values()):
                errors.append(f"blank_required_value:row_{row_number}")
                continue
            if not ID_PATTERN.fullmatch(row["hospital_id"].strip()):
                errors.append(f"invalid_hospital_id:row_{row_number}")
            for column in CODE_COLUMNS.intersection(row):
                if not CODE_PATTERN.fullmatch(row[column].strip()):
                    errors.append(f"{column}_must_be_controlled_code:row_{row_number}")
            if "id_procedimento" in row and not PROCEDURE_PATTERN.fullmatch(row["id_procedimento"].strip()):
                errors.append(f"invalid_procedure_code:row_{row_number}")

            for column in contract["dates"]:
                try:
                    fmt = "%Y-%m" if column == "ano_mes" else "%Y-%m-%d"
                    pattern = r"^\d{4}-(0[1-9]|1[0-2])$" if column == "ano_mes" else r"^\d{4}-\d{2}-\d{2}$"
                    if not re.fullmatch(pattern, row[column]):
                        raise ValueError
                    datetime.strptime(row[column], fmt)
                except ValueError:
                    errors.append(f"invalid_date:{column}:row_{row_number}")

            for column in contract["integers"]:
                try:
                    value = int(row[column])
                    if value < 0 or str(value) != row[column].strip():
                        raise ValueError
                except ValueError:
                    errors.append(f"invalid_nonnegative_integer:{column}:row_{row_number}")

            if contract_name == "bed_census":
                try:
                    operational = int(row["operational_beds"])
                    staffed = int(row["staffed_beds"])
                    occupied = int(row["occupied_beds"])
                    blocked = int(row["blocked_beds"])
                    if staffed > operational:
                        errors.append(f"staffed_exceeds_operational:row_{row_number}")
                    if blocked > operational:
                        errors.append(f"blocked_exceeds_operational:row_{row_number}")
                    if occupied > operational:
                        warnings.append("occupied_exceeds_operational_review_required")
                except ValueError:
                    pass

            for column in contract["decimals"]:
                try:
                    raw_value = row[column].strip()
                    value = Decimal(raw_value)
                    if not DECIMAL_PATTERN.fullmatch(raw_value) or not value.is_finite() or abs(value) > DECIMAL_MAX:
                        raise InvalidOperation
                except (InvalidOperation, ValueError):
                    errors.append(f"invalid_decimal:{column}:row_{row_number}")

            key = tuple(row[column].strip() for column in contract["key"])
            if key in seen_keys:
                errors.append(f"duplicate_business_key:row_{row_number}")
            seen_keys.add(key)

    if row_count == 0:
        errors.append("empty_data_file")
    return {"file": contract_name, "rows": row_count, "errors": errors, "warnings": sorted(set(warnings))}


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida CSVs agregados do piloto hospitalar sem ler dados individuais.")
    for name in CONTRACTS:
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, help=f"CSV {name} conforme o contrato documentado.")
    args = parser.parse_args()
    selected = {
        name: getattr(args, name)
        for name in CONTRACTS
        if getattr(args, name) is not None
    }
    if not selected:
        parser.error("informe ao menos um arquivo CSV do piloto")

    report = {
        "passed": True,
        "files": [validate_csv(name, path) for name, path in selected.items()],
    }
    report["passed"] = all(not item["errors"] for item in report["files"])
    print(json.dumps(report, ensure_ascii=False))
    if not report["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

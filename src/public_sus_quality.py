"""Quality gates for the public SIH/SUS, CNES and SISREG aggregates."""

from __future__ import annotations

import calendar
from typing import Mapping

import pandas as pd


YEAR = 2025
EXPECTED_MONTHS = {f"{YEAR}-{month:02d}" for month in range(1, 13)}
SIH_MONTHLY = "sih_publico_aih_mensal"
SIH_PROCEDURES = "sih_publico_aih_procedimento"
CNES_MONTHLY = "cnes_leitos_publicos_mensal"
OCCUPANCY_MONTHLY = "sih_ocupacao_estimada_mensal"
SISREG_PROCEDURES = "sisreg_fila_publica_procedimento"


def validate_public_aggregates(
    aggregates: Mapping[str, pd.DataFrame], *, require_complementary: bool = True
) -> dict[str, object]:
    """Return a compact validation report; errors block publication, warnings do not."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    def require_table(name: str) -> pd.DataFrame | None:
        frame = aggregates.get(name)
        if frame is None:
            errors.append(f"missing_table:{name}")
            return None
        if frame.empty:
            errors.append(f"empty_table:{name}")
            return None
        return frame

    def check_months(frame: pd.DataFrame, table: str) -> bool:
        if "ano_mes" not in frame:
            errors.append(f"missing_period_column:{table}")
            return False
        actual = set(frame["ano_mes"].astype(str))
        if actual != EXPECTED_MONTHS:
            errors.append(f"invalid_month_coverage:{table}")
            return False
        checks.append(f"12_months:{table}")
        return True

    monthly = require_table(SIH_MONTHLY)
    procedures = require_table(SIH_PROCEDURES)
    monthly_numeric: pd.DataFrame | None = None
    monthly_values_valid = False
    monthly_periods_valid = False
    if monthly is not None:
        if not {"ano_mes", "volume_aih", "aihs_com_valor"}.issubset(monthly.columns):
            errors.append(f"missing_columns:{SIH_MONTHLY}")
        else:
            monthly_periods_valid = check_months(monthly, SIH_MONTHLY)
            if monthly["ano_mes"].duplicated().any():
                errors.append(f"duplicate_key:{SIH_MONTHLY}")
            monthly_counts = monthly[["volume_aih", "aihs_com_valor"]].apply(
                pd.to_numeric, errors="coerce"
            )
            monthly_numeric = monthly_counts
            monthly_values_valid = not monthly_counts.isna().any().any() and not monthly_counts.lt(0).any().any()
            for column in ("volume_aih", "aihs_com_valor"):
                values = monthly_counts[column]
                if values.isna().any() or values.lt(0).any():
                    errors.append(f"invalid_nonnegative_values:{SIH_MONTHLY}.{column}")
                if values.notna().all() and values.mod(1).ne(0).any():
                    errors.append(f"invalid_integer_values:{SIH_MONTHLY}.{column}")
            if (monthly_counts["aihs_com_valor"] > monthly_counts["volume_aih"]).any():
                errors.append(f"value_count_exceeds_volume:{SIH_MONTHLY}")
            checks.append("sih_monthly_counts")

    if procedures is not None:
        required_columns = {"ano_mes", "id_procedimento", "volume_aih", "aihs_com_valor"}
        if not required_columns.issubset(procedures.columns):
            errors.append(f"missing_columns:{SIH_PROCEDURES}")
        else:
            procedure_numeric = procedures[["volume_aih", "aihs_com_valor"]].apply(
                pd.to_numeric, errors="coerce"
            )
            procedure_values_valid = not procedure_numeric.isna().any().any() and not procedure_numeric.lt(0).any().any()
            for column in ("volume_aih", "aihs_com_valor"):
                values = procedure_numeric[column]
                if values.isna().any() or values.lt(0).any():
                    errors.append(f"invalid_nonnegative_values:{SIH_PROCEDURES}.{column}")
                if values.notna().all() and values.mod(1).ne(0).any():
                    errors.append(f"invalid_integer_values:{SIH_PROCEDURES}.{column}")
            if (procedure_numeric["aihs_com_valor"] > procedure_numeric["volume_aih"]).any():
                errors.append(f"value_count_exceeds_volume:{SIH_PROCEDURES}")

            monthly_procedures = procedures.loc[procedures["ano_mes"].astype(str) != str(YEAR)]
            annual_procedures = procedures.loc[procedures["ano_mes"].astype(str) == str(YEAR)]
            if monthly_procedures.duplicated(["ano_mes", "id_procedimento"]).any():
                errors.append(f"duplicate_key:{SIH_PROCEDURES}:monthly")
            if annual_procedures.duplicated(["id_procedimento"]).any():
                errors.append(f"duplicate_key:{SIH_PROCEDURES}:annual")
            monthly_codes = set(monthly_procedures["id_procedimento"].dropna().astype(str))
            annual_codes = set(annual_procedures["id_procedimento"].dropna().astype(str))
            if annual_codes != monthly_codes:
                errors.append("sih_annual_procedure_codes_mismatch")
            if monthly is not None and {"ano_mes", "volume_aih"}.issubset(monthly.columns):
                expected_months_with_cases = set(
                    monthly.loc[
                        pd.to_numeric(monthly["volume_aih"], errors="coerce").gt(0), "ano_mes",
                    ].astype(str)
                )
                if set(monthly_procedures["ano_mes"].astype(str)) != expected_months_with_cases:
                    errors.append(f"invalid_month_coverage:{SIH_PROCEDURES}")
                can_reconcile = (
                    monthly_numeric is not None
                    and monthly_values_valid
                    and procedure_values_valid
                    and monthly_periods_valid
                    and not monthly["ano_mes"].duplicated().any()
                )
                if can_reconcile:
                    period_keys = procedures["ano_mes"].astype(str)
                    monthly_mask = period_keys.ne(str(YEAR))
                    procedure_totals = procedure_numeric.loc[monthly_mask].copy()
                    procedure_totals["ano_mes"] = period_keys.loc[monthly_mask]
                    monthly_sums = procedure_totals.groupby("ano_mes").sum(numeric_only=True)
                    expected_sums = monthly_numeric.copy()
                    expected_sums.index = monthly["ano_mes"].astype(str)
                    aligned = monthly_sums.reindex(expected_sums.index, fill_value=0)
                    for column in ("volume_aih", "aihs_com_valor"):
                        if not aligned[column].astype(float).reset_index(drop=True).equals(
                            expected_sums[column].astype(float).reset_index(drop=True)
                        ):
                            errors.append(f"sih_procedure_monthly_{column}_mismatch")
                        annual_sum = procedure_numeric.loc[~monthly_mask, column].sum()
                        if annual_sum != monthly_numeric[column].sum():
                            errors.append(f"sih_annual_procedure_{column}_mismatch")
                    checks.append("sih_procedure_reconciliation")

    required_complementary = {
        CNES_MONTHLY, OCCUPANCY_MONTHLY, SISREG_PROCEDURES,
    }
    if require_complementary:
        for table in sorted(required_complementary):
            if table not in aggregates:
                errors.append(f"missing_table:{table}")

    capacity = aggregates.get(CNES_MONTHLY)
    if capacity is not None and capacity.empty:
        errors.append(f"empty_table:{CNES_MONTHLY}")
        capacity = None
    if capacity is not None:
        if check_months(capacity, CNES_MONTHLY):
            if "uf" not in capacity.columns:
                errors.append(f"missing_columns:{CNES_MONTHLY}.uf")
            else:
                if capacity.duplicated(["ano_mes", "uf"]).any():
                    errors.append(f"duplicate_key:{CNES_MONTHLY}")
                if set(capacity["uf"].astype(str)) != {"AL"}:
                    errors.append(f"unexpected_uf:{CNES_MONTHLY}")
            numeric = [
                "estabelecimentos_hospitalares", "leitos_gerais_sus", "leitos_uti_sus", "total_leitos_sus",
            ]
            if any(column not in capacity for column in numeric):
                errors.append(f"missing_columns:{CNES_MONTHLY}")
            else:
                values = capacity[numeric].apply(pd.to_numeric, errors="coerce")
                if values.isna().any().any() or values.lt(0).any().any():
                    errors.append(f"invalid_nonnegative_values:{CNES_MONTHLY}")
                if values.notna().all().all() and values.mod(1).ne(0).any().any():
                    errors.append(f"invalid_integer_values:{CNES_MONTHLY}")
                if values["total_leitos_sus"].le(0).any():
                    errors.append(f"zero_capacity:{CNES_MONTHLY}")
                if not (values["leitos_gerais_sus"] + values["leitos_uti_sus"]).equals(values["total_leitos_sus"]):
                    errors.append(f"capacity_total_mismatch:{CNES_MONTHLY}")
            checks.append("cnes_capacity_consistency")

    occupancy = aggregates.get(OCCUPANCY_MONTHLY)
    if occupancy is not None and occupancy.empty:
        errors.append(f"empty_table:{OCCUPANCY_MONTHLY}")
        occupancy = None
    if occupancy is not None:
        occupancy_months_valid = check_months(occupancy, OCCUPANCY_MONTHLY)
        if occupancy_months_valid:
            if occupancy["ano_mes"].duplicated().any():
                errors.append(f"duplicate_key:{OCCUPANCY_MONTHLY}")
            required = {"dias_paciente_sih", "leitos_sus_cnes", "leitos_dia_disponiveis", "ocupacao_estimada_pct"}
            if not required.issubset(occupancy.columns):
                errors.append(f"missing_columns:{OCCUPANCY_MONTHLY}")
            else:
                numeric_columns = [
                    "dias_paciente_sih", "leitos_sus_cnes",
                    "leitos_dia_disponiveis", "ocupacao_estimada_pct",
                ]
                values = occupancy[numeric_columns].apply(pd.to_numeric, errors="coerce")
                numeric_valid = not values.isna().any().any() and not values.lt(0).any().any()
                if not numeric_valid:
                    errors.append(f"invalid_nonnegative_values:{OCCUPANCY_MONTHLY}")
                integer_columns = ["dias_paciente_sih", "leitos_sus_cnes", "leitos_dia_disponiveis"]
                if values[integer_columns].notna().all().all() and values[integer_columns].mod(1).ne(0).any().any():
                    errors.append(f"invalid_integer_values:{OCCUPANCY_MONTHLY}")
                if values["leitos_sus_cnes"].le(0).any() or values["leitos_dia_disponiveis"].le(0).any():
                    errors.append(f"zero_capacity:{OCCUPANCY_MONTHLY}")
                if numeric_valid and occupancy_months_valid:
                    expected_bed_days = pd.Series(
                        [
                            int(beds) * calendar.monthrange(YEAR, int(str(period)[-2:]))[1]
                            for period, beds in zip(occupancy["ano_mes"], values["leitos_sus_cnes"])
                        ],
                        index=occupancy.index,
                    )
                    if not expected_bed_days.equals(values["leitos_dia_disponiveis"].astype(int)):
                        errors.append(f"bed_day_denominator_mismatch:{OCCUPANCY_MONTHLY}")
                    expected_pct = (
                        values["dias_paciente_sih"] * 100 / values["leitos_dia_disponiveis"]
                    ).round(2)
                    if not expected_pct.equals(values["ocupacao_estimada_pct"].astype(float).round(2)):
                        errors.append(f"occupancy_formula_mismatch:{OCCUPANCY_MONTHLY}")
                if capacity is not None and {"uf", "ano_mes", "total_leitos_sus"}.issubset(capacity.columns):
                    al_capacity = capacity.loc[capacity["uf"].astype(str).eq("AL")].copy()
                    if al_capacity["ano_mes"].duplicated().any():
                        errors.append("duplicate_key:cnes_al_capacity_by_month")
                        expected_capacity = pd.Series(index=occupancy.index, dtype="float64")
                    else:
                        capacity_by_month = al_capacity.set_index("ano_mes")["total_leitos_sus"]
                        expected_capacity = occupancy["ano_mes"].map(capacity_by_month)
                    if expected_capacity.isna().any() or (
                        numeric_valid
                        and not expected_capacity.astype("float64").equals(
                            values["leitos_sus_cnes"].astype("float64")
                        )
                    ):
                        errors.append("occupancy_capacity_does_not_match_cnes")
                if values["ocupacao_estimada_pct"].gt(100).any():
                    warnings.append("occupancy_over_100_requires_review")
            checks.append("occupancy_formula_consistency")

    waiting = aggregates.get(SISREG_PROCEDURES)
    if waiting is not None and waiting.empty:
        errors.append(f"empty_table:{SISREG_PROCEDURES}")
        waiting = None
    if waiting is not None:
        required = {
            "data_extracao", "procedimento", "solicitacoes_pendentes",
            "espera_media_dias", "espera_mediana_dias", "espera_p90_dias", "espera_max_dias",
        }
        if not required.issubset(waiting.columns):
            errors.append(f"missing_columns:{SISREG_PROCEDURES}")
        else:
            if waiting.duplicated(["data_extracao", "procedimento"]).any():
                errors.append(f"duplicate_key:{SISREG_PROCEDURES}")
            if pd.to_datetime(waiting["data_extracao"], errors="coerce").isna().any():
                errors.append(f"invalid_snapshot_date:{SISREG_PROCEDURES}")
            waiting_metrics = waiting[[
                "solicitacoes_pendentes", "espera_media_dias", "espera_mediana_dias",
                "espera_p90_dias", "espera_max_dias",
            ]].apply(pd.to_numeric, errors="coerce")
            if waiting_metrics.isna().any().any() or waiting_metrics.lt(0).any().any():
                errors.append(f"invalid_nonnegative_values:{SISREG_PROCEDURES}")
            if waiting_metrics.notna().all().all() and waiting_metrics.mod(1).ne(0).any().any():
                errors.append(f"invalid_integer_values:{SISREG_PROCEDURES}")
            if waiting_metrics["solicitacoes_pendentes"].lt(30).any():
                errors.append(f"suppression_threshold_breached:{SISREG_PROCEDURES}")
            if (waiting_metrics["espera_max_dias"] < waiting_metrics["espera_p90_dias"]).any() or (
                waiting_metrics["espera_p90_dias"] < waiting_metrics["espera_mediana_dias"]
            ).any():
                errors.append(f"waiting_percentile_order_invalid:{SISREG_PROCEDURES}")
            checks.append("sisreg_suppression_and_percentiles")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }

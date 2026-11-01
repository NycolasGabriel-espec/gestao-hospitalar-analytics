import calendar
import unittest

import pandas as pd

from src.public_sus_quality import validate_public_aggregates


def valid_aggregates():
    months = [f"2025-{month:02d}" for month in range(1, 13)]
    monthly = pd.DataFrame([
        {
            "ano_mes": month,
            "volume_aih": 1,
            "dias_permanencia": 2,
            "permanencia_media_dias": 2.0,
            "valor_aih_total": 10.0,
            "aihs_com_valor": 1,
        }
        for month in months
    ])
    procedure_rows = [
        {
            "ano_mes": month,
            "id_procedimento": "0000000001",
            "volume_aih": 1,
            "dias_permanencia": 2,
            "permanencia_media_dias": 2.0,
            "valor_aih_total": 10.0,
            "aihs_com_valor": 1,
        }
        for month in months
    ]
    procedure_rows.append({
        "ano_mes": "2025",
        "id_procedimento": "0000000001",
        "volume_aih": 12,
        "dias_permanencia": 24,
        "permanencia_media_dias": 2.0,
        "valor_aih_total": 120.0,
        "aihs_com_valor": 12,
    })
    capacity = pd.DataFrame([
        {
            "ano_mes": month,
            "uf": "AL",
            "estabelecimentos_hospitalares": 20,
            "leitos_gerais_sus": 90,
            "leitos_uti_sus": 10,
            "total_leitos_sus": 100,
        }
        for month in months
    ])
    occupancy = pd.DataFrame([
        {
            "ano_mes": month,
            "dias_paciente_sih": 2,
            "leitos_sus_cnes": 100,
            "leitos_dia_disponiveis": 100 * calendar.monthrange(2025, int(month[-2:]))[1],
            "ocupacao_estimada_pct": round(
                2 * 100 / (100 * calendar.monthrange(2025, int(month[-2:]))[1]), 2
            ),
        }
        for month in months
    ])
    waiting = pd.DataFrame([{
        "data_extracao": "2025-08-10",
        "procedimento": "Procedimento sintético",
        "solicitacoes_pendentes": 30,
        "espera_media_dias": 11,
        "espera_mediana_dias": 10,
        "espera_p90_dias": 12,
        "espera_max_dias": 15,
    }])
    return {
        "sih_publico_aih_mensal": monthly,
        "sih_publico_aih_procedimento": pd.DataFrame(procedure_rows),
        "cnes_leitos_publicos_mensal": capacity,
        "sih_ocupacao_estimada_mensal": occupancy,
        "sisreg_fila_publica_procedimento": waiting,
    }


class PublicSusQualityTests(unittest.TestCase):
    def test_valid_aggregates_pass_all_gates(self):
        report = validate_public_aggregates(valid_aggregates())
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["errors"], [])

    def test_missing_month_and_duplicate_aih_key_block_publication(self):
        aggregates = valid_aggregates()
        aggregates["sih_publico_aih_mensal"] = aggregates["sih_publico_aih_mensal"].iloc[:-1]
        aggregates["sih_publico_aih_procedimento"] = pd.concat([
            aggregates["sih_publico_aih_procedimento"],
            aggregates["sih_publico_aih_procedimento"].iloc[[0]],
        ], ignore_index=True)

        report = validate_public_aggregates(aggregates)

        self.assertFalse(report["passed"])
        self.assertIn("invalid_month_coverage:sih_publico_aih_mensal", report["errors"])
        self.assertIn("duplicate_key:sih_publico_aih_procedimento:monthly", report["errors"])

    def test_small_sisreg_groups_are_rejected(self):
        aggregates = valid_aggregates()
        aggregates["sisreg_fila_publica_procedimento"].loc[0, "solicitacoes_pendentes"] = 29

        report = validate_public_aggregates(aggregates)

        self.assertFalse(report["passed"])
        self.assertIn(
            "suppression_threshold_breached:sisreg_fila_publica_procedimento",
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()

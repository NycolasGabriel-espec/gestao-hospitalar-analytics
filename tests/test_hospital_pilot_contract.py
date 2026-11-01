import csv
import tempfile
import unittest
from pathlib import Path

from src.validate_hospital_pilot import validate_csv


class HospitalPilotContractTests(unittest.TestCase):
    def write_csv(self, columns, rows):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "pilot.csv"
        with path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.writer(destination)
            writer.writerow(columns)
            writer.writerows(rows)
        return path

    def test_valid_aggregated_bed_census_passes(self):
        path = self.write_csv(
            [
                "hospital_id", "observation_date", "shift_code", "sector_code", "bed_type",
                "operational_beds", "staffed_beds", "occupied_beds", "blocked_beds",
            ],
            [["hospital-01", "2026-10-31", "day", "ward-a", "adult", "30", "28", "24", "2"]],
        )

        report = validate_csv("bed_census", path)

        self.assertEqual(report["errors"], [])
        self.assertEqual(report["rows"], 1)

    def test_unapproved_patient_identifier_column_is_rejected(self):
        path = self.write_csv(
            [
                "hospital_id", "observation_date", "shift_code", "sector_code", "bed_type",
                "operational_beds", "staffed_beds", "occupied_beds", "blocked_beds", "patient_name",
            ],
            [["hospital-01", "2026-10-31", "day", "ward-a", "adult", "30", "28", "24", "2", "Example"]],
        )

        report = validate_csv("bed_census", path)

        self.assertIn("header_must_match_contract_exactly", report["errors"])


if __name__ == "__main__":
    unittest.main()

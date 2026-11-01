import unittest
from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from src.extract_sih_sus import extract_sih_data, normalize_source_frame


class ExtractionTests(unittest.TestCase):
    def test_mixed_source_dates_have_the_same_canonical_format(self):
        frame = pd.DataFrame({'N_AIH': ['synthetic-a', 'synthetic-b'], 'DT_INTER': [date(2025, 1, 2), '20250103'], 'IDADE': [50.0, '51'], 'UNUSED_FIELD': ['discard', 'discard']})
        normalized = normalize_source_frame(frame)
        self.assertEqual(normalized.DT_INTER.tolist(), ['20250102', '20250103'])
        self.assertEqual(normalized.IDADE.tolist(), ['50', '51'])
        self.assertNotIn('UNUSED_FIELD', normalized)
        with TemporaryDirectory() as folder:
            normalized.to_parquet(f'{folder}/source.parquet', index=False)
            self.assertEqual(len(pd.read_parquet(f'{folder}/source.parquet')), 2)

    def test_missing_month_prevents_an_incomplete_dataset(self):
        with TemporaryDirectory() as folder, patch('src.extract_sih_sus.pysus.ftp.sih', return_value=pd.DataFrame()), patch('src.extract_sih_sus.fetch_official_sih', return_value=pd.DataFrame()):
            with self.assertRaisesRegex(RuntimeError, '2025-05'):
                extract_sih_data('AL', 2025, [5], output_dir=folder)


if __name__ == '__main__':
    unittest.main()

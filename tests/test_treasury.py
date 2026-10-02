import unittest

import pandas as pd

from treasury import cents, daily_balances, prepare, read_fec


def fec(rows, name='test.txt'):
    header = 'JournalCode\tEcritureDate\tCompteNum\tDebit\tCredit\n'
    return read_fec((header + '\n'.join('\t'.join(row) for row in rows)).encode(), name)


class TreasuryTests(unittest.TestCase):
    def test_two_years_with_only_initial_opening(self):
        df = fec([
            ('AN', '20250101', '512001', '1000', '0'),
            ('BQ', '20250101', '512001', '0', '100'),
            ('BQ', '20251231', '512001', '0', '200'),
            ('AN', '20260101', '512001', '700', '0'),
            ('BQ', '20260102', '512001', '50', '0'),
        ])
        kept, audit = prepare(df, ['512001'], ['AN'], '2025-01-01')
        result = daily_balances(kept, ['512001'], '2025-01-01', '2026-01-03')
        self.assertEqual(len(result), 368)
        self.assertEqual(result.loc['2025-01-01', 'Total'], 900)
        self.assertEqual(result.loc['2026-01-01', 'Total'], 700)
        self.assertEqual(result.iloc[-1]['Total'], 750)
        self.assertEqual(audit.Decision.str.startswith('Exclue').sum(), 1)

    def test_later_restart_and_custom_journal(self):
        df = fec([('RAN', '20250101', '512A', '1000', '0'),
                  ('BQ', '20251231', '512A', '0', '200'),
                  ('RAN', '20260101', '512A', '800', '0'),
                  ('BQ', '20260101', '512A', '0', '50')])
        kept, _ = prepare(df, ['512A'], ['RAN'], '2026-01-01')
        result = daily_balances(kept, ['512A'], '2026-01-01', '2026-01-04')
        self.assertTrue(result.Total.eq(750).all())

    def test_combined_minimum_and_bank_selection(self):
        df = fec([('AN', '20260101', '512A', '100', '0'),
                  ('AN', '20260101', '512B', '0', '0'),
                  ('BQ', '20260102', '512A', '0', '100'),
                  ('BQ', '20260102', '512B', '100', '0')])
        kept, _ = prepare(df, ['512A', '512B'], ['AN'], '2026-01-01')
        result = daily_balances(kept, ['512A', '512B'], '2026-01-01', '2026-01-03')
        self.assertEqual(result.Total.min(), 100)
        self.assertEqual(result[['512A', '512B']].min().sum(), 0)
        kept, _ = prepare(df, ['512A'], ['AN'], '2026-01-01')
        self.assertEqual(daily_balances(kept, ['512A'], '2026-01-01', '2026-01-03').Total.min(), 0)

    def test_invalid_input_does_not_silently_become_zero(self):
        for value in ['oops', 'NaN', 'Infinity', '1.001', '1,234.56']:
            with self.assertRaises(ValueError):
                cents(value)
        self.assertEqual(cents('1\u202f234,56'), 123456)
        self.assertEqual(cents('-20,05'), -2005)
        with self.assertRaises(ValueError):
            fec([('BQ', '20260230', '512', '10', '0')])

    def test_encoding_delimiter_and_account_preservation(self):
        data = 'JournalCode;EcritureDate;CompteNum;Debit;Credit;CompteLib\nAN;01/01/2026;0512A;1 234,56;;Banque été'
        for encoding in ('cp1252', 'utf-8-sig', 'utf-16'):
            df = read_fec(data.encode(encoding), 'test.csv')
            self.assertEqual(df.iloc[0].CompteNum, '0512A')
            self.assertEqual(df.iloc[0].MouvementCentimes, 123456)

    def test_identical_rows_preserved_and_negative_balance(self):
        df = fec([('BQ', '20260101', '512', '0', '10')] * 2)
        kept, _ = prepare(df, ['512'], [], '2026-01-01')
        self.assertEqual(daily_balances(kept, ['512'], '2026-01-01', '2026-01-02').Total.min(), -20)


if __name__ == '__main__':
    unittest.main()

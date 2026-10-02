import io
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def upload(name, rows):
    f = io.BytesIO(('JournalCode;EcritureDate;CompteNum;Debit;Credit\n' + rows).encode())
    f.name = name
    return f


class AppTests(unittest.TestCase):
    def test_full_multi_fec_flow_and_exports(self):
        files = [upload('2025.csv', 'AN;20250101;512A;1000;0\nBQ;20251231;512A;0;200'),
                 upload('2026.csv', 'AN;20260101;512A;800;0\nBQ;20260102;512A;50;0')]
        with patch('streamlit.file_uploader', return_value=files):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
            self.assertFalse(app.exception)
            app.checkbox[1].check().run()
            self.assertFalse(app.exception)
            app.checkbox[2].check().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, '800,00 €')
            self.assertEqual(len(app.get('plotly_chart')), 2)
            self.assertEqual(len(app.get('download_button')), 2)
            self.assertEqual(app.dataframe[-1].value.iloc[-1]['Total'], 850)

    def test_overlapping_fec_blocked(self):
        files = [upload('a.csv', 'AN;20250101;512A;1000;0\nBQ;20251231;512A;0;200'),
                 upload('b.csv', 'AN;20250101;512A;1000;0\nBQ;20250601;512A;50;0')]
        with patch('streamlit.file_uploader', return_value=files):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
            self.assertFalse(app.exception)
            self.assertIn('chevauchent', app.error[0].value)
            self.assertEqual(len(app.get('plotly_chart')), 0)


if __name__ == '__main__':
    unittest.main()

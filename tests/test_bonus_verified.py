import unittest
from unittest.mock import patch

from scripts.bonus_verified import chart_answer, chart_interval, chart_values, direct_grid


class VerifiedEvidenceTests(unittest.TestCase):
    def test_merged_power_columns_remain_distinct(self):
        row = {"label": "A3", "group": "Khu A", "columns": [("Ptt (kW)", "5553"), ("Stt (kVA)", "6170")]}
        self.assertEqual(direct_grid("Công suất kVA của A3?", [row]), ("6170 kVA.", row, "Stt (kVA)"))
        self.assertEqual(direct_grid("Công suất kW của A3?", [row]), ("5553 kW.", row, "Ptt (kW)"))
        self.assertIsNone(direct_grid("Giá điện của A3 theo công suất kVA?", [row]))

    def test_subgroup_prefers_a_matching_named_row(self):
        rows = [
            {"label": "Khu C", "group": "Khu C", "columns": [("Khối lượng CTR (Tấn/ngày) 2045", "134,1")]},
            {"label": "CTR công nghiệp", "group": "Khu C", "columns": [("Khối lượng CTR (Tấn/ngày) 2045", "26,6")]},
        ]
        hit = direct_grid("CTR công nghiệp ở Khu C năm 2045 bao nhiêu tấn/ngày?", rows)
        self.assertEqual(hit[0], "26,6 Tấn/ngày.")
        self.assertIsNone(direct_grid("CTR công nghiệp ở Khu C năm 2050 bao nhiêu tấn/ngày?", rows))

    def test_chart_calculation_uses_source_operands(self):
        source = {"text": "Trục ngang từ trái sang phải: Xã M 4.321 người; Xã N 2.100 người. Các số in dưới cột."}
        self.assertEqual(chart_values(source), {"Xã M": 4321, "Xã N": 2100})
        with patch("scripts.bonus_verified.complete") as model:
            answer, event = chart_answer("Chênh lệch giữa cột cao nhất và thấp nhất?", source, "unused")
            model.assert_not_called()
        self.assertEqual(answer, "2.221 người (Xã M − Xã N).")
        self.assertEqual(event["operands"], {"Xã M": 4321, "Xã N": 2100})

    def test_chart_axes_and_bands_use_different_operations(self):
        with patch("scripts.bonus_verified.complete") as model:
            source = {"text": "Trục ngang từ trái sang phải: Xã M 4.321 người. Các số in dưới cột."}
            answer, event = chart_answer("Khoảng cách giữa hai vạch chia trên trục tung?", source, "unused")
            self.assertIsNone(answer)
            self.assertEqual(event["plan"], {"action": "visual"})
            model.assert_not_called()
        self.assertEqual(chart_interval("Xã nào dưới vạch 10.000 người và trên 9.000 người?"), (9000, 10000))

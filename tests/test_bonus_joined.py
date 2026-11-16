import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.bonus_joined import chain_recorded, choose, dependent_answer, verify_freeze


class JoinedBenchmarkTests(unittest.TestCase):
    def test_figure_label_controls_the_second_lookup(self):
        figure = {"id": "figure", "kind": "image", "text": "Khu A xanh, Khu B đỏ."}
        red = {"id": "red-row", "kind": "table", "label": "Khu B", "group": "Khu B",
               "columns": [("Ptt (kW)", "11")]}
        blue = {"id": "blue-row", "kind": "table", "label": "Khu A", "group": "Khu A",
                "columns": [("Ptt (kW)", "22")]}

        class StubIndex:
            grids = [(('', 'phu tai dien', (), 0), [red, blue])]

            def candidates(self, query):
                return [red, blue], "grid"

        events = []
        with patch("scripts.bonus_joined.complete", return_value=({"action": "bind", "label": "Khu B"}, {})):
            answer, citations = dependent_answer("tên khu màu đỏ", "Hình 6", "bảng phụ tải điện",
                                                "Ptt (kW)", [figure], StubIndex(), "unused", events)
        self.assertEqual(answer, "Khu B: 11 kW.")
        trace = {"events": events, "citations": citations, "question": "Tra Ptt của vùng màu đỏ."}
        self.assertTrue(chain_recorded(trace, {"entity": "Khu B"}))
        self.assertFalse(chain_recorded(trace, {"entity": "Khu A"}))
        events[3]["query"] = "Tra số không có nhãn vừa đọc"
        self.assertFalse(chain_recorded(trace, {"entity": "Khu B"}))

    def test_freeze_rejects_changed_review_and_selects_a_verified_chain(self):
        metrics = {"parallel": {"verified_chains": 0, "chain_cases": 4, "passed": 22},
                   "dependent": {"verified_chains": 4, "chain_cases": 4, "passed": 21,
                                 "by_group": {"multi": {"passed": 4}}, "errors": 0, "median_seconds": 3}}
        self.assertEqual(choose(metrics), "dependent")
        record = {"identity": "fixed", "dev_files": {"dependent.review.json": "old"},
                  "dev_metrics": metrics, "selected": "dependent"}
        with (patch("scripts.bonus_joined.read", side_effect=[record, "fixed"]),
              patch("scripts.bonus_joined.reviewed_dev", return_value=({"dependent.review.json": "new"}, metrics))):
            with self.assertRaisesRegex(ValueError, "reviewed dev evidence changed"):
                verify_freeze(Path("unused"), "fixed")

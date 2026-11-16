import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.bonus_passages import passage_score, phrases, score, visual_choice


class PassageTests(unittest.TestCase):
    def test_specific_subject_outweighs_a_general_topic_overlap(self):
        requested = phrases("Nước thải công nghiệp được xử lý theo hệ thống riêng hay chung?")
        general = {"text": "Hệ thống thoát nước mưa và nước thải của đô thị hiện hữu."}
        specific = {"text": "Nước thải công nghiệp được thu gom và xử lý theo các hệ thống riêng."}
        self.assertGreater(passage_score(specific, requested), passage_score(general, requested))

    def test_visual_option_requires_only_one_exact_label(self):
        question = "Trong số Bắc Giang và Bắc Ninh, tỉnh nào có nhãn ở Hình 1?"

        class StubIndex:
            rows = [{"text": "Các nhãn gồm Bắc Ninh và Hưng Yên."}]

            def candidates(self, query):
                return self.rows, "figure"

        index = StubIndex()
        self.assertEqual(visual_choice(question, index)[0], "Bắc Ninh")
        index.rows = [{"text": "Bắc Ninh và Bắc Giang đều có nhãn ở phía đông."}]
        self.assertIsNone(visual_choice(question, index))

    def test_score_counts_failed_cases_in_group_total(self):
        cases = [{"id": label, "group": "table"} for label in ("A", "B")]
        traces = [{"id": case["id"], "status": "answered", "elapsed_seconds": 1, "cost_usd": 0}
                  for case in cases]
        records = {
            "passages.json": traces,
            "passages.review.json": {"trace_sha256": "trace", "labels": [
                {"id": "A", "passed": True, "reason": "Exact row"},
                {"id": "B", "passed": False, "reason": "Wrong column"},
            ]},
            "selection.json": {"identity": "freeze"},
            "fingerprint.json": "freeze",
        }
        with (patch("scripts.bonus_passages.cases", return_value=cases),
              patch("scripts.bonus_passages.read", side_effect=lambda path: records[path.name]),
              patch("scripts.bonus_passages.digest", return_value="trace"),
              patch("scripts.bonus_passages.write") as output,
              patch("builtins.print")):
            score(Path("unused"))
        self.assertEqual(output.call_args.args[1]["by_group"], {"table": {"passed": 1, "total": 2}})

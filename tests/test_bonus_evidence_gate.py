"""Exercise the PDF agent's deterministic evidence checks."""
import unittest
from importlib.util import find_spec
from unittest.mock import patch


@unittest.skipUnless(find_spec("fastembed"), "Requires the bonus retrieval dependencies")
class BonusEvidenceGateTests(unittest.TestCase):
    def test_absent_subject_cannot_inherit_another_labels_attribute(self):
        from scripts.bonus_refined import validate_answer

        result = {"citations": [{"text": "Lưu vực 1 ở phía trên. Lưu vực 2 ở phía dưới."}],
                  "answer": "Phía dưới."}
        with patch("scripts.bonus_refined.complete") as model:
            refs, event = validate_answer("Lưu vực 3 nằm ở đâu?", result, "")
        self.assertEqual(refs, [])
        self.assertEqual(event["missing_subjects"], ["luu vuc 3"])
        model.assert_not_called()

    def test_power_measurement_does_not_support_a_currency_rate(self):
        from scripts.bonus_refined import validate_answer

        result = {"citations": [{"text": "Ô A2 có phụ tải 25316 kW."}], "answer": "25316"}
        with patch("scripts.bonus_refined.complete") as model:
            refs, event = validate_answer("Giá điện ô A2 bao nhiêu đồng/kWh?", result, "")
        self.assertEqual(refs, [])
        self.assertEqual(event["reason"], "requested_currency_unit_absent")
        model.assert_not_called()

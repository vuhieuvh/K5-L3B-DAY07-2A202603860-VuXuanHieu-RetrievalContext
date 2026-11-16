import unittest

from scripts.bonus_scoped import missing_dimension, ordered_value, scope_hits


class ScopedBonusTests(unittest.TestCase):
    def test_numeric_fields_require_matching_dimensions(self):
        power = [{"text": "Ô A7 | Ptt (kW): 8086 | Stt (kVA): 8985"}]
        self.assertIsNone(missing_dimension("Công suất biểu kiến kVA của A7?", power))
        self.assertIsNotNone(missing_dimension("Điện áp kV của A7?", power))
        population = [{"text": "Tổng dân số xã Ô Diên: 14.626 người."}]
        self.assertIsNotNone(missing_dimension("Mật độ dân số của xã Ô Diên?", population))

    def test_sequence_reads_the_item_between_named_anchors(self):
        left_to_right = [{"text": "Trục từ trái sang phải: ghế đỏ, ghế xanh, ghế trắng."}]
        question = "Màu nào nằm ngay giữa ghế đỏ và ghế trắng?"
        self.assertEqual(ordered_value(question, left_to_right)[0], "ghế xanh")
        arrows = [{"text": "Tuyến nước: cống → trạm bơm → bể lắng → trạm xử lý."}]
        question = "Công trình ngay sau trạm bơm và trước trạm xử lý là gì?"
        self.assertEqual(ordered_value(question, arrows)[0], "bể lắng")

    def test_named_section_overrides_a_semantically_similar_appendix(self):
        actual = {"id": "S1", "page": 14, "kind": "text", "text": "Phạm vi ranh giới nghiên cứu:"}
        appendix = {"id": "S2", "page": 322, "kind": "text", "text": "Phạm vi được phê duyệt"}

        class StubIndex:
            rows = [actual, appendix]

            def candidates(self, question, theme):
                return [appendix, actual], "text"

        hits, route = scope_hits(StubIndex(), "Mục Phạm vi ranh giới nghiên cứu, phía Bắc giáp gì?", "")
        self.assertEqual((hits, route), ([actual], "section"))

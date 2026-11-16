"""Check query-only PDF modality routing and multipart decomposition."""
import unittest
from importlib.util import find_spec


@unittest.skipUnless(find_spec("fastembed"), "Requires the bonus retrieval dependencies")
class BonusRoutingTests(unittest.TestCase):
    def setUp(self):
        self.document = [
            {"page": 12, "kind": "text"},
            {"page": 12, "kind": "image", "title": "Hình 1. Bản đồ"},
            {"page": 20, "kind": "table"},
            {"page": 20, "kind": "chart"},
            {"page": 180, "kind": "ocr"},
        ]

    def test_accented_table_word_does_not_match_transport_preposition(self):
        from bonus.index import scope

        self.assertIn(0, scope("Đi bằng đường sắt trong bao lâu?", self.document))
        self.assertEqual(scope("Trong bảng có bao nhiêu dòng?", self.document), [2])

    def test_chart_figure_and_appendix_are_available_in_query_scope(self):
        from bonus.index import scope

        self.assertEqual(scope("Đơn vị trong biểu đồ là gì?", self.document), [3])
        self.assertEqual(scope("Quan sát Hình 1 thấy gì?", self.document), [1])
        self.assertIn(4, scope("Phụ lục nói về khu vực nào?", self.document))

    def test_numbered_parts_are_searched_independently(self):
        from bonus.benchmark import query_parts

        question = "Đối chiếu: (1) Hình 1 có gì? (2) Dân số nêu bao nhiêu?"
        self.assertEqual(query_parts(question, True), ["Hình 1 có gì?", "Dân số nêu bao nhiêu?"])
        self.assertEqual(query_parts(question, False), [question])

    def test_numbered_table_uses_matching_caption_despite_ocr_spacing(self):
        from bonus.index import scope

        rows = [
            {"page": 20, "kind": "table", "text": "Bảng 7.6- 3: Chỉ tiêu"},
            {"page": 21, "kind": "table", "text": "Bảng 7.6- 4: Khối lượng"},
        ]
        self.assertEqual(scope("Bảng 7.6-4 ghi gì?", rows), [1])

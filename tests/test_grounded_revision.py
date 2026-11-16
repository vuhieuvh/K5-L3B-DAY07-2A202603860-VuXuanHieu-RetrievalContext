import unittest

from src.grounding import recover_scoped_quote, scope_chunks, validate_quote


def chunk(label, page, start, text):
    return {"id": label, "source_id": "fixture", "page": page, "text": text,
            "metadata": {"article": [19], "start": start, "end": start + len(text)}}


class GroundedRevisionTests(unittest.TestCase):
    def test_clause_keeps_continuation_and_its_source_offsets(self):
        other = chunk("earlier", 1, 0, "Điều 19. Hội đồng 1. Ít nhất 3 thành viên.")
        anchor = chunk("anchor", 2, 0, "5. Chương trình tài năng: Hội")
        tail = chunk("tail", 2, anchor["metadata"]["end"] + 1, "đồng gồm 5 người, trong đó có 2 phản biện.")
        question = "Theo khoản 5 Điều 19, Hội đồng có bao nhiêu người và phản biện?"
        scoped, anchors = scope_chunks(question, [other], [tail, other, anchor])
        self.assertEqual(scoped, [anchor, tail])
        self.assertEqual(anchors, ["anchor"])
        self.assertIsNone(validate_quote(question, "5 người, 2 phản biện", "Hội đồng gồm 5 người, trong đó có 2 phản biện.", scoped))
        quote = "Hội đồng chấm luận văn gồm 5 người, trong đó có 2 phản biện."
        self.assertIsNotNone(recover_scoped_quote(question, "5 người, 2 phản biện", quote, scoped))
        self.assertIsNone(recover_scoped_quote(question, "7 người, 2 phản biện", quote, scoped))

    def test_points_cannot_be_used_as_money(self):
        quote = "Giải nhất: 0,10 điểm."
        row = chunk("award", 1, 0, quote)
        self.assertEqual(validate_quote("Giải nhất được thưởng bao nhiêu đồng?", "0,10 đồng", quote, [row]),
                         "requested_currency_not_supported")
        self.assertIsNone(validate_quote("Giải nhất được cộng bao nhiêu điểm?", "0,10 điểm", quote, [row]))
        self.assertEqual(validate_quote("Giải nhất được cộng bao nhiêu điểm?", "0,20 điểm", quote, [row]),
                         "quoted_values_do_not_support_answer")

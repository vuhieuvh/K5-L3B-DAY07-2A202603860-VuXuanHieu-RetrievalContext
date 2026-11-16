"""Regression tests for benchmark evidence integrity and lookup failures."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.benchmark import (
    digest, evaluate, prepare_reviews, read, reserve_test_outputs, review_binding, run_case,
    verify_frozen_dev, write,
)


class BenchmarkProtocolTests(unittest.TestCase):
    def test_test_outputs_cannot_be_reopened(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            public, private = root / "results/test", root / "full/test"
            reserve_test_outputs(public, private)
            sentinel = public / "dense.json"
            sentinel.write_text("old trace", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                reserve_test_outputs(public, private)
            with self.assertRaises(FileExistsError):
                reserve_test_outputs(root / "new/test", private)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "old trace")

    def test_review_cannot_follow_same_id_and_citation_count_into_a_new_trace(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            trace = root / "results/dev/dense.json"
            reviews = root / "reviews"
            write(trace.parent / "summary.json", {"results": {"dense": {}}})
            row = {"query_id": "D01", "agent": {
                "status": "answered", "answer": "Original answer", "citations": ["same-id"],
            }}
            write(trace, [row])
            args = SimpleNamespace(output=root / "results", reviews=reviews)
            with patch("src.benchmark.load_cases", return_value=[{"id": "D01", "answerable": True}]):
                prepare_reviews(args, "dev")
            review = reviews / "dev_dense.json"
            _, labels, receipt = review_binding(trace, review)
            self.assertIsNone(labels[0]["answer_grade"])
            frozen = {"identity": {}, "dev_review_sha256": ""}
            summary = trace.parent / "review_summary.json"
            write(summary, {"dense": {"binding": receipt}})
            frozen["dev_review_sha256"] = digest(summary)
            verify_frozen_dev(args, frozen, {})
            payload = read(review)
            payload["reviews"][0]["reason"] = "Changed after freeze"
            write(review, payload)
            with self.assertRaisesRegex(ValueError, "changed after freeze"):
                verify_frozen_dev(args, frozen, {})
            row["agent"]["answer"] = "New answer"
            write(trace, [row])
            with self.assertRaisesRegex(ValueError, "does not match the exact trace"):
                review_binding(trace, review)

    def test_original_lookup_failure_is_written_and_next_case_runs(self):
        cases = [
            {"id": "D01", "question": "First question", "answerable": False},
            {"id": "D02", "question": "Second question", "answerable": False},
        ]
        retriever = Mock(chunks=[])
        retriever.search.side_effect = [OSError("index offline"), []]
        with TemporaryDirectory() as folder:
            root = Path(folder)
            args = SimpleNamespace(output=root / "results", private=root / "full",
                                   base_url="http://localhost", retrieval_only=True, config=None)
            with patch("src.benchmark.load_cases", return_value=cases):
                evaluate(args, "dev", ["lexical"], retriever, {})
            output = args.output / "retrieval_dev"
            failed, succeeded = read(output / "lexical.json")
            self.assertEqual(failed["original_query_error"]["stage"], "original_query")
            self.assertIsNone(succeeded["original_query_error"])
            self.assertEqual(read(output / "summary.json")["results"]["lexical"]
                             ["original_query_errors"], 1)
        retriever.search.side_effect = OSError("index offline")
        failed = run_case(cases[0], object(), retriever, "dense")
        self.assertEqual(failed["agent"]["status"], "error")
        self.assertIsNone(failed["agent"]["answer"])

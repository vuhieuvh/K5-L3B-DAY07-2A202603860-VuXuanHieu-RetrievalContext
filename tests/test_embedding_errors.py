"""Exercise real ONNX exception classes at the query embedding boundary."""
import unittest
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agent import CONFIGS, run_agent
from src.benchmark import evaluate, read


@unittest.skipUnless(find_spec("fastembed"), "Requires the Day 7 retrieval dependencies")
class EmbeddingFailureTests(unittest.TestCase):
    def test_onnx_embedding_failures_are_logged_and_next_case_runs(self):
        from onnxruntime.capi import onnxruntime_pybind11_state as ort
        from src.retrieval import Retrieval

        def failing_embedding(error_type):
            yield from ()
            raise error_type("embedding backend unavailable")

        cases = [
            {"id": "D01", "question": "First question", "answerable": False},
            {"id": "D02", "question": "Second question", "answerable": False},
        ]
        usage = {"prompt_tokens": 5, "completion_tokens": 2}
        for error_type in (ort.Fail, ort.RuntimeException, ort.InvalidArgument):
            with self.subTest(error=error_type.__name__), TemporaryDirectory() as folder:
                root = Path(folder)
                args = SimpleNamespace(output=root / "results", private=root / "full",
                                       base_url="http://localhost", retrieval_only=False, config=None)
                retriever = Retrieval.__new__(Retrieval)
                retriever.chunks = []
                retriever.client = Mock()
                retriever.client.query_points.return_value.points = []
                vector = Mock()
                vector.tolist.return_value = [0.0] * 384
                retriever.embedder = Mock()
                retriever.embedder.embed.side_effect = [
                    failing_embedding(error_type), iter([vector]), iter([vector]),
                ]
                model = Mock()
                model.decide.side_effect = [
                    ({"action": "search"}, usage), ({"action": "abstain"}, usage),
                ]
                with patch("src.benchmark.load_cases", return_value=cases), patch(
                    "src.benchmark.LlamaModel", return_value=model,
                ):
                    evaluate(args, "dev", ["dense"], retriever, {})
                path = args.output / "dev"
                failed, succeeded = read(path / "dense.json")
                self.assertEqual(failed["agent"]["status"], "error")
                self.assertEqual(failed["agent"]["reason"], "EmbeddingError")
                self.assertIn(error_type.__name__, failed["original_query_error"]["message"])
                self.assertEqual(succeeded["agent"]["status"], "abstain")
                self.assertEqual(read(path / "summary.json")["results"]["dense"]
                                 ["original_query_errors"], 1)

    def test_agent_logs_onnx_failure_in_hybrid_search(self):
        from onnxruntime.capi import onnxruntime_pybind11_state as ort
        from src.retrieval import Retrieval

        retriever = Retrieval.__new__(Retrieval)
        retriever.embedder = Mock()
        retriever.embedder.embed.side_effect = ort.Fail("embedding backend unavailable")
        model = Mock()
        model.decide.return_value = {"action": "search"}, {}
        trace = run_agent("A question", model, retriever, CONFIGS["hybrid"])
        self.assertEqual(trace["status"], "error")
        self.assertEqual(trace["reason"], "EmbeddingError")
        self.assertIn("(Fail)", trace["events"][-1]["message"])
        self.assertIsNone(trace["answer"])

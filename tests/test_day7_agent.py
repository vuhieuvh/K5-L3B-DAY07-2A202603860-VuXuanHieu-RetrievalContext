"""Regression checks for agent actions, citation scope and loop termination."""
import unittest

from src.agent import Config, run_agent


class ScriptedModel:
    def __init__(self, *actions):
        self.actions = iter(actions)

    def decide(self, question, context, queries, remaining):
        return next(self.actions), {"prompt_tokens": 0, "completion_tokens": 0}


class FixtureRetriever:
    def __init__(self):
        self.queries = []

    def search(self, query, method, limit):
        self.queries.append(query)
        return [{
            "id": str(len(self.queries)), "source_id": "fixture", "page": 1,
            "text": "Có 5 người." if len(self.queries) == 2 else "Khóa luận.",
            "metadata": {"article": [1]},
        }]


class Day7AgentTests(unittest.TestCase):
    def test_new_evidence_can_be_added_and_cited_after_second_search(self):
        model = ScriptedModel(
            {"action": "search"},
            {"action": "search", "query": "số người"},
            {"action": "answer", "answer": "Có 5 người.", "citations": ["C1"]},
        )
        retriever = FixtureRetriever()
        result = run_agent("Hội đồng có bao nhiêu người?", model, retriever, Config("dense"))
        self.assertEqual(retriever.queries, ["Hội đồng có bao nhiêu người?", "số người"])
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["citations"], ["2"])
        self.assertIn("[2]", result["answer"])
        self.assertEqual(result["context_label_to_id"], {"C1": "2", "C2": "1"})

    def test_out_of_context_citation_is_rejected(self):
        model = ScriptedModel(
            {"action": "search"},
            {"action": "answer", "answer": "Có 5 người.", "citations": ["C5"]},
        )
        result = run_agent("Câu hỏi", model, FixtureRetriever(), Config("dense"))
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["reason"], "invalid_or_missing_citations")
        self.assertEqual(result["citations"], [])

    def test_repeated_search_stops(self):
        model = ScriptedModel({"action": "search"}, {"action": "search", "query": "câu hỏi"})
        retriever = FixtureRetriever()
        result = run_agent("Câu hỏi", model, retriever, Config("dense"))
        self.assertEqual(retriever.queries, ["Câu hỏi"])
        self.assertEqual(result["reason"], "repeated_query")

    def test_provider_error_is_reported_as_an_error(self):
        class UnavailableModel:
            def decide(self, question, context, queries, remaining):
                raise TimeoutError("local server timed out")

        result = run_agent("Câu hỏi", UnavailableModel(), FixtureRetriever(), Config("dense"))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason"], "TimeoutError")
        self.assertIsNone(result["answer"])

"""Retrieve sentence-level evidence within the requested part of the planning PDF."""
import argparse
import re
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from bonus.ingest import ROOT, SOURCE_SHA, sha
from scripts import bonus_scoped as scoped
from src.benchmark import digest, read, shareable, write


TEST = ROOT / "data/bonus_passages_test.json"


def phrases(text):
    terms = scoped.key(text).split()
    return {" ".join(terms[i:i + size]): size for size in range(2, 7)
            for i in range(len(terms) - size + 1)}


def passage_score(row, requested):
    body = " " + scoped.key(row["text"]) + " "
    matching = [length for phrase, length in requested.items() if f" {phrase} " in body]
    return max(matching, default=0), sum(length ** 2 for length in matching)


class PassageIndex(scoped.previous.EvidenceIndex):
    def candidates(self, question, topic=""):
        hits, route = super().candidates(question, topic)
        if route != "text":
            return hits, route
        requested = phrases(question)
        explicit_appendix = re.search(r"\b(phu luc|quyet dinh|nhiem vu quy hoach)\b", scoped.key(question))
        best = []
        for row in self.rows:
            if row["kind"] not in {"text", "ocr"}:
                continue
            if (row["page"] <= 163) == bool(explicit_appendix):
                continue
            for text in row["text"].splitlines():
                if len(text) < 28:
                    continue
                passage = {**row, "text": text}
                score = passage_score(passage, requested)
                if score[0] >= 3:
                    best.append((score, passage))
        best.sort(key=lambda item: item[0], reverse=True)
        if not best:
            return hits, route
        # Keep a short set of distinct passages so competing sections cannot
        # inject a similar number from a different subject into the prompt.
        distinct = {}
        for _, passage in best:
            distinct.setdefault(scoped.key(passage["text"]), passage)
        return list(distinct.values())[:3], "text"


def visual_choice(question, index):
    match = re.search(r"^\s*Trong số (.+?) và (.+?),", question, re.IGNORECASE)
    if not match or not re.search(r"\bcó nhãn\b", question, re.IGNORECASE):
        return None
    hits, route = index.candidates(question)
    if route != "figure":
        return None
    matching = [(choice, row) for choice in match.groups() for row in hits
                if scoped.contains(row["text"], choice)]
    if len(matching) == 1:
        name, row = matching[0]
        return name, [row], [{"event": "search", "route": route, "query": question, "candidates": hits},
                             {"event": "read_label", "choices": list(match.groups()), "value": name}]
    return None


def respond(question, index, endpoint):
    started = perf_counter()
    parts = re.split(r"\s*\(\d+\)\s*", question)
    theme, questions = (parts[0], parts[1:]) if len(parts) > 2 else ("", [question])
    answers, citations, events = [], [], []
    status = "answered"
    try:
        for part in questions:
            answer, sources, steps = visual_choice(part, index) or scoped.resolve(part, theme, index, endpoint)
            answers.append(answer)
            citations.extend(sources)
            events.extend(steps)
            if not sources:
                status = "abstain"
            theme = " ".join([theme, *(row["title"] for row in sources
                                      if row["kind"] == "image" and row.get("title"))]).strip()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, IndexError) as error:
        events.append({"event": "error", "type": type(error).__name__, "message": str(error)})
        status = "error"
    return {"question": question, "status": status, "events": events,
            "answer": " ".join(answers) if status == "answered" else scoped.REFUSAL,
            "citations": citations if status == "answered" else [],
            "elapsed_seconds": perf_counter() - started, "cost_usd": 0}


def cases(split):
    history = scoped.cases("dev")
    if split == "dev":
        failures = {"S07", "S19", "S20"}
        return history[:18] + [r for r in history if r["id"] in {"R24", "RN20", "RV24"}] + [
            {**row, "split": "dev", "id": "R" + row["id"]}
            for row in scoped.cases("test") if row["id"] in failures]
    rows = read(TEST)
    distribution = {"table": 6, "image": 5, "chart": 5, "multi": 4, "text": 4, "missing": 6}
    previous = scoped.previous
    history += scoped.cases("test") + previous.cases_for("test") + previous.benchmark("test") + previous.split_cases("test")
    if (Counter(row["group"] for row in rows) != distribution or len({row["id"] for row in rows}) != len(rows)
            or any(row["split"] != "test" for row in rows)
            or {scoped.key(row["question"]) for row in rows} & {scoped.key(row["question"]) for row in history}):
        raise ValueError("Invalid independent test")
    return rows


def fingerprint(args, split):
    base = scoped.fingerprint(args, "test")
    base["passage_source_sha256"] = digest(Path(__file__))
    return {**base, "passage_test_sha256": digest(TEST)} if split == "test" else base


def score(folder):
    path = folder / "test/passages.json"
    review_path = path.with_name("passages.review.json")
    review = read(review_path)
    if (review["trace_sha256"] != digest(path) or read(folder / "selection.json")["identity"]
            != read(path.with_name("fingerprint.json"))):
        raise ValueError("Trace or frozen identity mismatch")
    traces = read(path)
    groups = {}
    for case, row, label in zip(cases("test"), traces, review["labels"], strict=True):
        if not case["id"] == row["id"] == label["id"] or not label["reason"] or type(label["passed"]) is not bool:
            raise ValueError("Invalid review")
        if label["passed"] and row["status"] != ("abstain" if case["group"] == "missing" else "answered"):
            raise ValueError("Incorrect passing status")
        group = groups.setdefault(case["group"], {"passed": 0, "total": 0})
        group["passed"] += label["passed"]
    times = [row["elapsed_seconds"] for row in traces]
    passed = sum(group["passed"] for group in groups.values())
    result = {"passed": passed, "total": len(traces), "rate": passed / len(traces), "by_group": groups,
              "errors": sum(row["status"] == "error" for row in traces), "total_seconds": sum(times),
              "median_seconds": median(times), "cost_usd": sum(row["cost_usd"] for row in traces),
              "trace_sha256": digest(path), "review_sha256": digest(review_path)}
    write(path.with_name("summary.json"), result)
    print(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("dev", "freeze", "test", "score-test"))
    parser.add_argument("--index", type=Path, default=ROOT / ".local/bonus")
    parser.add_argument("--output", type=Path, default=ROOT / "results/bonus_passages")
    parser.add_argument("--full", type=Path, default=ROOT / ".local/bonus/passages")
    parser.add_argument("--pdf", type=Path, default=ROOT.parent / "phan-doan-2.pdf")
    parser.add_argument("--server", type=Path, default=ROOT / ".local/llama-vulkan/llama-server.exe")
    parser.add_argument("--weights", type=Path, default=ROOT / ".local/qwen3-4b-instruct-2507-q4_k_m.gguf")
    parser.add_argument("--embedding", type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8090")
    args = parser.parse_args()
    if args.phase == "score-test":
        return score(args.output)
    if not args.embedding or sha(args.pdf) != SOURCE_SHA:
        parser.error("Expected the assigned PDF and --embedding")
    selection = args.output / "selection.json"
    if args.phase == "freeze":
        if selection.exists():
            raise FileExistsError(selection)
        cases("test")
        dev = args.output / "dev"
        if fingerprint(args, "dev") != read(dev / "fingerprint.json"):
            raise ValueError("Development identity differs from freeze")
        write(selection, {"identity": fingerprint(args, "test"), "dev_trace_sha256": digest(dev / "passages.json")})
        return
    split = args.phase
    identity = fingerprint(args, split)
    if split == "test" and identity != read(selection)["identity"]:
        raise ValueError("Test identity differs from freeze")
    public = args.output / split
    local = args.full / split
    public.mkdir(parents=True, exist_ok=False)
    local.mkdir(parents=True, exist_ok=False)
    index = PassageIndex(args.index, args.embedding, args.pdf)
    rows = []
    for case in cases(split):
        row = {"id": case["id"], **respond(case["question"], index, args.endpoint)}
        rows.append(row)
        write(local / "passages.json", rows)
        write(public / "passages.partial.json", shareable(rows))
        print(split, row["id"], row["status"], round(row["elapsed_seconds"], 2), flush=True)
    (public / "passages.partial.json").replace(public / "passages.json")
    write(public / "fingerprint.json", identity)


if __name__ == "__main__":
    main()

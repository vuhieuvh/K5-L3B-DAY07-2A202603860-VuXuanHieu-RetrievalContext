"""Run the Day 7 benchmark and freeze the configuration before evaluating test."""
import argparse
import hashlib
import json
import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.parse import urlparse

from starter.agent_metrics import aggregate

from .agent import CONFIGS, LlamaModel, pack, run_agent
from .retrieval import COLLECTION, EMBEDDING, WEIGHTS, Retrieval

ROOT = Path(__file__).resolve().parents[1]
CRITERION = (
    "On dev only, exclude configurations with model/store errors. Maximize manually "
    "graded grounded-answer mean, then sufficiency of final context, then correct "
    "abstentions, then median agent latency (ms, rounded to nearest millisecond). "
    "Use dense, lexical, hybrid, hybrid_context order for exact ties."
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def digest(path, *, binary=False):
    content = path.read_bytes() if binary else path.read_text(encoding="utf-8").encode()
    return hashlib.sha256(content).hexdigest()


def matches(chunk, ref):
    meta = chunk["metadata"]
    return (chunk["source_id"] == ref["source_id"] and chunk["page"] == ref["page"]
            and ref["article"] in meta["article"] and meta["start"] <= ref["start"]
            and meta["end"] >= ref["end"]
            and chunk["text"][ref["start"] - meta["start"]:ref["end"] - meta["start"]]
            == ref["evidence"])


def evidence_hits(chunks, case):
    return [any(matches(chunk, ref) for chunk in chunks for ref in group)
            for group in case.get("evidence_groups", [])]


def load_cases(split):
    rows = read(ROOT / "data" / f"benchmark_{split}.json")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate benchmark ID")
    counts = Counter(row["answerable"] for row in rows)
    if counts[True] < (15 if split == "dev" else 5) or counts[False] < 2:
        raise ValueError(f"Incomplete {split} benchmark")
    if any(row["split"] != split or not row["question"].strip() for row in rows):
        raise ValueError(f"Invalid {split} benchmark")
    return rows


def identity(args, retriever):
    corpus = json.dumps(retriever.chunks, ensure_ascii=False, sort_keys=True).encode()
    pipeline = [*(ROOT / "src").glob("*.py"), *(ROOT / "starter").glob("*.py")]
    return {
        "source_id": sorted({chunk["source_id"] for chunk in retriever.chunks}),
        "pages": len({chunk["page"] for chunk in retriever.chunks}),
        "chunks": len(retriever.chunks),
        "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
        "collection": COLLECTION,
        "index_file_sha256": digest(
            args.index / "collection" / COLLECTION / "storage.sqlite", binary=True,
        ),
        "embedding": EMBEDDING,
        "embedding_dimensions": 384,
        "embedding_weights_sha256": digest(args.embedding / WEIGHTS, binary=True),
        "agent_model": args.model,
        "runtime": args.runtime,
        "agent_weights_sha256": digest(args.model_file, binary=True) if args.model_file else None,
        "pipeline": {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(pipeline)},
        "configs": {key: asdict(config) for key, config in CONFIGS.items()},
        "benchmark_dev_sha256": digest(ROOT / "data/benchmark_dev.json"),
        "benchmark_test_sha256": digest(ROOT / "data/benchmark_test.json"),
    }


def shareable(obj):
    """Preserve order, references and scores; omit full corpus passages from public traces."""
    if isinstance(obj, list):
        return [shareable(value) for value in obj]
    if isinstance(obj, dict):
        return {key: shareable(value) for key, value in obj.items() if key != "text"}
    return obj


def fraction(n, total):
    return {"n": n, "N": total, "rate": n / total if total else None}


def summarize(traces, real_agent):
    answerable = [trace for trace in traces if trace["hit3"] is not None]
    total = len(answerable)
    elapsed = [trace["agent"]["elapsed_ms"] for trace in traces if trace["agent"] is not None]
    calls = Counter(sum(event["event"] == "search" for event in trace["agent"]["events"])
                    for trace in traces if trace["agent"] is not None)
    usage = [event["usage"] for trace in traces if trace["agent"] is not None
             for event in trace["agent"]["events"] if event["event"] == "model"]

    def token_total(key):
        if usage and all(event[key] is not None for event in usage):
            return sum(event[key] for event in usage)
        return None

    return {
        "cases": len(traces),
        "hit1": fraction(sum(trace["hit1"] for trace in answerable), total),
        "hit3": fraction(sum(trace["hit3"] for trace in answerable), total),
        "first_pack_evidence_rate": fraction(
            sum(trace["first_pack_has_all_evidence"] for trace in answerable), total,
        ),
        "context_evidence_rate": fraction(
            sum(trace["final_context_has_all_evidence"] for trace in answerable), total,
        ) if real_agent else None,
        "median_original_retrieval_ms": median(trace["retrieval_ms"] for trace in traces),
        "median_agent_ms": median(elapsed) if elapsed else None,
        "total_agent_ms": sum(elapsed) if elapsed else None,
        "search_count_distribution": dict(sorted(calls.items())) if real_agent else None,
        "agent_errors": sum(trace["agent"]["status"] == "error"
                            for trace in traces if trace["agent"] is not None) if real_agent else None,
        "prompt_tokens": token_total("prompt_tokens"),
        "completion_tokens": token_total("completion_tokens"),
    }


def evaluate(args, split, names, retriever, fingerprint):
    cases = load_cases(split)
    for case in cases:
        coverage = evidence_hits(retriever.chunks, case)
        if case["answerable"] and (not coverage or not all(coverage)):
            raise ValueError(f"{case['id']} has unreachable gold in {COLLECTION}")
    model = None if args.retrieval_only else LlamaModel(args.base_url, os.environ.get("DAY7_API_KEY"))
    local = urlparse(args.base_url).hostname in ("localhost", "127.0.0.1", "::1")
    folder = args.output / ("retrieval_dev" if args.retrieval_only else split)
    summary_path = folder / "summary.json"
    results = {}
    if summary_path.exists():
        previous = read(summary_path)
        if previous["identity"] == fingerprint:
            results = previous["results"]
        elif args.config:
            raise ValueError("Use a fresh output directory for different experiment inputs")
    for name in names:
        config = CONFIGS[name]
        traces = []
        for case in cases:
            query = case["question"]
            started = perf_counter()
            candidates = retriever.search(query, config.method, max(3, config.top_k))
            lookup_ms = (perf_counter() - started) * 1000
            _, first_cited = pack(candidates[:config.top_k], config.budget_chars)
            result = run_agent(query, model, retriever, config) if model else None
            has_gold = case["answerable"]
            traces.append({
                "query_id": case["id"], "question": query,
                "trial": name, "retrieval_ms": lookup_ms, "original_query_filter": None,
                "original_query_results": candidates,
                "hit1": any(evidence_hits(candidates[:1], case)) if has_gold else None,
                "hit3": any(evidence_hits(candidates[:3], case)) if has_gold else None,
                "first_pack_has_all_evidence": all(evidence_hits(first_cited.values(), case))
                if has_gold else None,
                "final_context_has_all_evidence": all(evidence_hits(result["context_chunks"], case))
                if has_gold and result else None,
                "agent": result,
            })
            if result:
                print(f"{split} {name} {case['id']} {result['status']} "
                      f"{result['elapsed_ms']/1000:.2f}s", flush=True)
        summary = {
            **summarize(traces, model is not None), "config": asdict(config),
            "service_cost_usd": 0 if local or model is None else None,
        }
        write(args.private / folder.name / f"{name}.json", traces)
        write(folder / f"{name}.json", shareable(traces))
        results[name] = summary
        write(summary_path, {"identity": fingerprint, "results": results})
        print(f"{split} {name} complete", flush=True)


def collect_reviews(args, split):
    cases = load_cases(split)
    folder = args.output / split
    run = read(folder / "summary.json")
    results = {}
    for name, summary in run["results"].items():
        traces = read(folder / f"{name}.json")
        labels = read(args.reviews / f"{split}_{name}.json")
        labels_by_id = {row["query_id"]: row for row in labels}
        expected = {row["query_id"] for row in traces if row["agent"]["status"] != "error"}
        if set(labels_by_id) != expected or any(not row.get("reason") for row in labels):
            raise ValueError(f"{split}/{name}: review every successful case and record reasons")
        grades = Counter()
        for case in cases:
            if case["answerable"] and case["id"] in labels_by_id:
                grade = labels_by_id[case["id"]].get("context_grade")
                if type(grade) is not int or grade not in (0, 1, 2):
                    raise ValueError(f"{case['id']}: expected context grade 0–2")
                grades[grade] += 1
        agent_traces = [dict(row["agent"], query_id=row["query_id"]) for row in traces]
        results[name] = {
            **aggregate(cases, agent_traces, labels),
            "context_grades": {str(i): grades[i] for i in range(3)},
            "measured": summary,
        }
    write(folder / "review_summary.json", results)
    return results


def freeze(args):
    folder = args.output / "dev"
    run = read(folder / "summary.json")
    if set(run["results"]) != set(CONFIGS):
        raise ValueError("Run and review all dev configurations first")
    results = collect_reviews(args, "dev")
    eligible = [name for name in CONFIGS if not results[name]["provider_errors"]]
    if not eligible:
        raise ValueError("No complete dev configuration without errors")

    def ranking(name):
        item = results[name]
        measured = item["measured"]
        return (item["grounded_answer"]["mean"], item["context_grades"]["2"],
                item["abstention"]["n"], -round(measured["median_agent_ms"]))

    chosen = max(eligible, key=ranking)
    record = {
        "selected": chosen, "baseline": "dense", "criterion": CRITERION,
        "frozen_at": datetime.now().astimezone().isoformat(),
        "identity": run["identity"], "dev_review_sha256": digest(folder / "review_summary.json"),
    }
    path = args.output / "selection.json"
    if path.exists():
        raise FileExistsError(f"Selection already exists: {path}. Use a fresh output directory.")
    write(path, record)
    print(f"Frozen dev selection: {chosen}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("dev", "test", "freeze", "review-dev", "review-test", "ask"))
    parser.add_argument("--index", type=Path, default=ROOT / ".local/qdrant")
    parser.add_argument("--embedding", type=Path, default=ROOT / ".local/e5")
    parser.add_argument("--output", type=Path, default=ROOT / "results")
    parser.add_argument("--private", type=Path, default=ROOT / ".local/traces")
    parser.add_argument("--reviews", type=Path, default=ROOT / "reviews")
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--model", default="qwen2.5-3b")
    parser.add_argument("--model-file", type=Path)
    parser.add_argument("--runtime", default="llama.cpp b8259")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--config", choices=CONFIGS)
    parser.add_argument("--question")
    args = parser.parse_args()
    if args.retrieval_only and args.phase != "dev":
        parser.error("--retrieval-only is available on dev only")
    if args.config and args.phase not in ("dev", "ask"):
        parser.error("--config is available on dev or ask")
    if args.phase == "freeze":
        freeze(args)
        return
    if args.phase.startswith("review-"):
        collect_reviews(args, args.phase.removeprefix("review-"))
        return
    if args.phase == "ask" and not (args.question and args.question.strip()):
        parser.error("ask requires --question")
    retriever = Retrieval(args.index, args.embedding)
    try:
        if args.phase == "ask":
            model = LlamaModel(args.base_url, os.environ.get("DAY7_API_KEY"))
            report = run_agent(args.question, model, retriever, CONFIGS[args.config or "dense"])
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        fingerprint = identity(args, retriever)
        if args.phase == "dev":
            if not args.retrieval_only and (args.output / "selection.json").exists():
                raise FileExistsError("Use a fresh output directory for additional trials after freeze")
            names = (args.config,) if args.config else CONFIGS
        else:
            record = read(args.output / "selection.json")
            if (record["identity"] != fingerprint
                    or record["dev_review_sha256"] != digest(args.output / "dev/review_summary.json")):
                raise ValueError("Test inputs differ from the dev freeze")
            names = tuple(dict.fromkeys((record["baseline"], record["selected"])))
        evaluate(args, args.phase, names, retriever, fingerprint)
    finally:
        retriever.close()


if __name__ == "__main__":
    main()

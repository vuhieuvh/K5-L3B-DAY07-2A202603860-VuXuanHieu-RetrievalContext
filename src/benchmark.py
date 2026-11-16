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

from .agent import CONFIGS, REVISED_CONFIGS, LlamaModel, pack, run_agent

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


def read_with_digest(path):
    content = path.read_text(encoding="utf-8")
    return json.loads(content), hashlib.sha256(content.encode("utf-8")).hexdigest()


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


def suite_configs(args):
    if getattr(args, "suite", "original") == "revised":
        return (CONFIGS | REVISED_CONFIGS) if getattr(args, "retrieval_only", False) else REVISED_CONFIGS
    return CONFIGS


def case_path(split, suite):
    prefix = "benchmark_revised" if suite == "revised" else "benchmark"
    return ROOT / "data" / f"{prefix}_{split}.json"


def load_cases(split, suite="original"):
    rows = read(case_path(split, suite))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate benchmark ID")
    counts = Counter(row["answerable"] for row in rows)
    if counts[True] < (15 if split == "dev" else 5) or counts[False] < 2:
        raise ValueError(f"Incomplete {split} benchmark")
    if any(row["split"] != split or not row["question"].strip() for row in rows):
        raise ValueError(f"Invalid {split} benchmark")
    if suite == "revised" and split == "test":
        used = load_cases("dev", suite) + load_cases("test")
        if {row["question"].casefold() for row in rows} & {row["question"].casefold() for row in used}:
            raise ValueError("Revised test must use questions outside development and the historical test")
    return rows


def identity(args, retriever):
    from .retrieval import COLLECTION, EMBEDDING, WEIGHTS

    corpus = json.dumps(retriever.chunks, ensure_ascii=False, sort_keys=True).encode()
    pipeline = [*(ROOT / "src").glob("*.py"), *(ROOT / "starter").glob("*.py")]
    suite = getattr(args, "suite", "original")
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
        "suite": suite,
        "configs": {key: asdict(config) for key, config in suite_configs(args).items()},
        "benchmark_dev_sha256": digest(case_path("dev", suite)),
        "benchmark_test_sha256": digest(case_path("test", suite)),
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


def run_case(case, model, retriever, name):
    config = (CONFIGS | REVISED_CONFIGS)[name]
    query = case["question"]
    started = perf_counter()
    lookup_error = None
    try:
        candidates = retriever.search(query, config.method, max(3, config.top_k))
    except (OSError, RuntimeError, ValueError, TypeError, KeyError, IndexError) as error:
        lookup_error = {"event": "error", "stage": "original_query",
                        "type": type(error).__name__, "message": str(error)}
        candidates = []
    lookup_ms = (perf_counter() - started) * 1000
    _, first_cited = pack(candidates[:config.top_k], config.budget_chars)
    result = None
    if model is not None:
        if lookup_error is None:
            result = run_agent(query, model, retriever, config)
        else:
            result = {
                "status": "error", "reason": lookup_error["type"], "answer": None,
                "citations": [], "events": [lookup_error], "context": [], "context_chunks": [],
                "context_label_to_id": {}, "elapsed_ms": lookup_ms,
            }
    has_gold = case["answerable"]
    return {
        "query_id": case["id"], "question": query, "trial": name,
        "retrieval_ms": lookup_ms, "original_query_filter": None,
        "original_query_error": lookup_error, "original_query_results": candidates,
        "hit1": any(evidence_hits(candidates[:1], case)) if has_gold else None,
        "hit3": any(evidence_hits(candidates[:3], case)) if has_gold else None,
        "first_pack_has_all_evidence": all(evidence_hits(first_cited.values(), case))
        if has_gold else None,
        "final_context_has_all_evidence": all(evidence_hits(result["context_chunks"], case))
        if has_gold and result else None,
        "agent": result,
    }


def reserve_test_outputs(public, private):
    if public.resolve() == private.resolve():
        raise ValueError("Public and full test traces require separate directories")
    if public.exists() or private.exists():
        raise FileExistsError("Test output already exists. Use a fresh output and private directory.")
    public.mkdir(parents=True, exist_ok=False)
    private.mkdir(parents=True, exist_ok=False)


def evaluate(args, split, names, retriever, fingerprint):
    cases = load_cases(split, getattr(args, "suite", "original"))
    for case in cases:
        coverage = evidence_hits(retriever.chunks, case)
        if case["answerable"] and (not coverage or not all(coverage)):
            raise ValueError(f"{case['id']} has unreachable gold in the index")
    local = urlparse(args.base_url).hostname in ("localhost", "127.0.0.1", "::1")
    folder = args.output / ("retrieval_dev" if args.retrieval_only else split)
    if split == "test":
        reserve_test_outputs(folder, args.private / split)
    summary_path = folder / "summary.json"
    results = {}
    if summary_path.exists():
        previous = read(summary_path)
        if previous["identity"] == fingerprint:
            results = previous["results"]
        elif args.config:
            raise ValueError("Use a fresh output directory for different experiment inputs")
    for name in names:
        config = suite_configs(args)[name]
        model = None if args.retrieval_only else LlamaModel(args.base_url, os.environ.get("DAY7_API_KEY"),
                                                           grounded=config.grounded)
        traces = []
        for case in cases:
            trace = run_case(case, model, retriever, name)
            traces.append(trace)
            result = trace["agent"]
            if result:
                print(f"{split} {name} {case['id']} {result['status']} "
                      f"{result['elapsed_ms']/1000:.2f}s", flush=True)
        summary = {
            **summarize(traces, model is not None), "config": asdict(config),
            "service_cost_usd": 0 if local or model is None else None,
            "original_query_errors": sum(row["original_query_error"] is not None for row in traces),
        }
        write(args.private / folder.name / f"{name}.json", traces)
        write(folder / f"{name}.json", shareable(traces))
        results[name] = summary
        write(summary_path, {"identity": fingerprint, "results": results})
        print(f"{split} {name} complete", flush=True)


def prepare_reviews(args, split):
    folder = args.output / split
    run = read(folder / "summary.json")
    cases = {row["id"]: row for row in load_cases(split, getattr(args, "suite", "original"))}
    for name in run["results"]:
        output = args.reviews / f"{split}_{name}.json"
        if output.exists():
            raise FileExistsError(f"Review already exists: {output}")
    for name in run["results"]:
        trace_path = folder / f"{name}.json"
        traces, trace_sha = read_with_digest(trace_path)
        rows = []
        for trace in traces:
            agent = trace["agent"]
            if agent["status"] == "error":
                continue
            cid = trace["query_id"]
            label = {"query_id": cid, "citation_support": [None] * len(agent["citations"]),
                     "reason": ""}
            if cases[cid]["answerable"]:
                label.update(answer_grade=None, context_grade=None)
            else:
                label["abstention_correct"] = None
            rows.append(label)
        write(args.reviews / f"{split}_{name}.json",
              {"trace_sha256": trace_sha, "reviews": rows})


def review_binding(trace_path, review_path):
    traces, trace_sha = read_with_digest(trace_path)
    payload, review_sha = read_with_digest(review_path)
    if not isinstance(payload, dict) or payload.get("trace_sha256") != trace_sha:
        raise ValueError(f"Review does not match the exact trace: {review_path}. Prepare a fresh review.")
    return traces, payload["reviews"], {"trace_sha256": trace_sha, "review_sha256": review_sha}


def collect_reviews(args, split):
    cases = load_cases(split, getattr(args, "suite", "original"))
    folder = args.output / split
    run = read(folder / "summary.json")
    results = {}
    for name, summary in run["results"].items():
        trace_path = folder / f"{name}.json"
        traces, labels, binding = review_binding(trace_path, args.reviews / f"{split}_{name}.json")
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
            "binding": binding,
        }
    write(folder / "review_summary.json", results)
    return results


def freeze(args):
    path = args.output / "selection.json"
    if path.exists():
        raise FileExistsError(f"Selection already exists: {path}. Use a fresh output directory.")
    folder = args.output / "dev"
    run = read(folder / "summary.json")
    configs = suite_configs(args)
    if set(run["results"]) != set(configs):
        raise ValueError("Run and review all dev configurations first")
    results = collect_reviews(args, "dev")
    eligible = [name for name in configs if not results[name]["provider_errors"]]
    criterion = CRITERION
    if getattr(args, "suite", "original") == "revised":
        def passed_regressions(name):
            _, labels, _ = review_binding(folder / f"{name}.json", args.reviews / f"dev_{name}.json")
            grades = {row["query_id"]: row for row in labels}
            scoped, money = grades.get("D18", {}), grades.get("D19", {})
            return (scoped.get("answer_grade") == scoped.get("context_grade") == 2
                    and bool(scoped.get("citation_support")) and all(scoped["citation_support"])
                    and money.get("abstention_correct") is True)

        eligible = [name for name in eligible if passed_regressions(name)]
        criterion = "Require both dev regression cases D18 and D19 to pass. " + criterion
    if not eligible:
        raise ValueError("No dev configuration met the eligibility criteria")

    def ranking(name):
        item = results[name]
        measured = item["measured"]
        return (item["grounded_answer"]["mean"], item["context_grades"]["2"],
                item["abstention"]["n"], -round(measured["median_agent_ms"]))

    chosen = max(eligible, key=ranking)
    record = {
        "selected": chosen, "baseline": "dense", "criterion": criterion,
        "frozen_at": datetime.now().astimezone().isoformat(),
        "identity": run["identity"], "dev_review_sha256": digest(folder / "review_summary.json"),
    }
    write(path, record)
    print(f"Frozen dev selection: {chosen}")


def verify_frozen_dev(args, record, fingerprint):
    folder = args.output / "dev"
    summary = folder / "review_summary.json"
    if record["identity"] != fingerprint or record["dev_review_sha256"] != digest(summary):
        raise ValueError("Test inputs differ from the dev freeze")
    for name, result in read(summary).items():
        _, _, binding = review_binding(folder / f"{name}.json", args.reviews / f"dev_{name}.json")
        if binding != result["binding"]:
            raise ValueError(f"Dev trace or review changed after freeze: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=(
        "dev", "test", "freeze", "prepare-review-dev", "prepare-review-test",
        "review-dev", "review-test", "ask",
    ))
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
    parser.add_argument("--suite", choices=("original", "revised"), default="original")
    parser.add_argument("--config", choices=CONFIGS | REVISED_CONFIGS)
    parser.add_argument("--question")
    args = parser.parse_args()
    configs = suite_configs(args)
    if args.config and args.config not in configs:
        parser.error("--config is unavailable in the selected suite")
    if args.retrieval_only and args.phase != "dev":
        parser.error("--retrieval-only is available on dev only")
    if args.config and args.phase not in ("dev", "ask"):
        parser.error("--config is available on dev or ask")
    if args.phase == "freeze":
        freeze(args)
        return
    if args.phase.startswith("prepare-review-"):
        prepare_reviews(args, args.phase.removeprefix("prepare-review-"))
        return
    if args.phase.startswith("review-"):
        if args.phase == "review-dev" and (args.output / "selection.json").exists():
            raise FileExistsError("Dev review is frozen. Use a fresh output directory.")
        collect_reviews(args, args.phase.removeprefix("review-"))
        return
    if args.phase == "ask" and not (args.question and args.question.strip()):
        parser.error("ask requires --question")
    from .retrieval import Retrieval

    retriever = Retrieval(args.index, args.embedding)
    try:
        if args.phase == "ask":
            config = configs[args.config or ("clause_grounded" if args.suite == "revised" else "dense")]
            model = LlamaModel(args.base_url, os.environ.get("DAY7_API_KEY"), grounded=config.grounded)
            report = run_agent(args.question, model, retriever, config)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        fingerprint = identity(args, retriever)
        if args.phase == "dev":
            if not args.retrieval_only and (args.output / "selection.json").exists():
                raise FileExistsError("Use a fresh output directory for additional trials after freeze")
            names = (args.config,) if args.config else configs
        else:
            record = read(args.output / "selection.json")
            verify_frozen_dev(args, record, fingerprint)
            names = tuple(dict.fromkeys((record["baseline"], record["selected"])))
        evaluate(args, args.phase, names, retriever, fingerprint)
    finally:
        retriever.close()


if __name__ == "__main__":
    main()

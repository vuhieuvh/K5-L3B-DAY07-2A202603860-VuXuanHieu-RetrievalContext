"""Evaluate dependent figure-to-table retrieval with a reviewed development lock."""
import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter

from bonus.benchmark import complete
from bonus.ingest import ROOT, SOURCE_SHA, sha
from scripts import bonus_passages as passages
from src.agent import action_variant
from src.benchmark import digest, read, shareable, write


DEV = ROOT / "data/bonus_joined_dev.json"
TEST = ROOT / "data/bonus_joined_test.json"
CONFIGS = ("parallel", "dependent")
SCOPED = passages.scoped
CHAIN = re.compile(r"^Trong (Hình \d+), xác định (.+?) rồi dùng (?:hạng mục|tên khu) đó tra (.+?) trong (bảng .+?)\.$", re.I)


def evidence_for_figure(figure, index):
    figures, _ = index.candidates(figure)
    return [row for row in figures if row["kind"] == "image"]


def parallel_answer(question, table, metric, figures, index, endpoint, events):
    tables, _ = index.candidates(f"Trong {table}, {metric} là bao nhiêu?")
    events.append({"event": "parallel_retrieval", "figures": figures, "tables": tables})
    if not figures or not tables:
        return SCOPED.REFUSAL, []
    refs = {f"S{i}": row for i, row in enumerate([*figures, *tables], 1)}
    schema = {"oneOf": [action_variant("abstain"), action_variant(
        "answer", answer={"type": "string"},
        sources={"type": "array", "minItems": 2, "maxItems": 2, "items": {"enum": list(refs)}})]}
    action, usage = complete(endpoint,
        "Trả lời bằng tiếng Việt dựa trên hình và bảng. Đọc nhãn theo mô tả, đối chiếu đúng hàng trong bảng. "
        "Dẫn đúng một nguồn hình và một nguồn bảng; từ chối nếu thiếu hàng đúng.",
        json.dumps({"question": question, "sources": {k: r["text"] for k, r in refs.items()}},
                   ensure_ascii=False), schema, 140)
    events.append({"event": "model", "proposal": action, "usage": usage})
    citations = [refs[key] for key in action.get("sources", [])]
    if {row["kind"] for row in citations} == {"image", "table"}:
        return action["answer"], citations
    return SCOPED.REFUSAL, []


def dependent_answer(selector, figure, table, metric, figures, index, endpoint, events):
    # Match labels from the document schema against the figure transcription.
    # The model sees only these visible labels, the selector and the figure.
    labels = {row["label"].lstrip("- ") for (_, pattern, _, _), records in index.grids
              if re.search(pattern, SCOPED.previous.normalize(table))
              for row in records if row["label"]}
    choices = {label: next(row for row in figures if SCOPED.contains(row["text"], label))
               for label in sorted(labels) if any(SCOPED.contains(row["text"], label) for row in figures)}
    events.append({"event": "hop_search_1", "query": f"{figure}: {selector}",
                   "candidates": figures, "visible_labels": list(choices)})
    if not choices:
        return SCOPED.REFUSAL, []
    schema = {"oneOf": [action_variant("abstain"), action_variant("bind", label={"enum": list(choices)})]}
    action, usage = complete(endpoint,
        "Xác định đúng tên đối tượng trong hình theo màu, vị trí hoặc chú giải được hỏi. "
        "Nếu rõ thì chọn đúng một nhãn trong danh sách. Từ chối nếu hình không xác định được duy nhất.",
        json.dumps({"selector": selector, "figure": [row["text"] for row in figures]},
                   ensure_ascii=False), schema, 70)
    events.append({"event": "hop_model", "usage": usage, "proposal": action})
    if action["action"] != "bind":
        return SCOPED.REFUSAL, []
    label = action["label"]
    figure_row = choices[label]
    query = f"Trong {table}, {metric} của {label} là bao nhiêu?"
    events.append({"event": "hop_bind", "value": label, "source_id": figure_row["id"], "next_query": query})
    hits, route = index.candidates(query)
    # Exclude sibling groups and rows whose entity is merely a substring.
    precise = [row for row in hits if SCOPED.key(row["label"]) == SCOPED.key(label)
               or SCOPED.key(row["group"]) == SCOPED.key(label)] if route == "grid" else []
    events.append({"event": "hop_search_2", "query": query, "candidates": precise})
    if result := SCOPED.previous.direct_grid(query, precise):
        answer, row, field = result
        events.append({"event": "hop_read_cell", "source_id": row["id"], "field": field, "entity": label})
        return f"{label}: {answer}", [figure_row, row]
    return SCOPED.REFUSAL, []


def respond(question, index, endpoint, config):
    match = CHAIN.fullmatch(question)
    if not match:
        return passages.respond(question, index, endpoint)
    figure, selector, metric, table = match.groups()
    started = perf_counter()
    events = []
    try:
        figures = evidence_for_figure(figure, index)
        if config == "dependent":
            answer, citations = dependent_answer(selector, figure, table, metric, figures, index, endpoint, events)
        else:
            answer, citations = parallel_answer(question, table, metric, figures, index, endpoint, events)
        status = "answered" if citations else "abstain"
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, IndexError) as error:
        events.append({"event": "error", "type": type(error).__name__, "message": str(error)})
        answer, citations, status = SCOPED.REFUSAL, [], "error"
    return {"question": question, "status": status, "events": events, "answer": answer,
            "citations": citations, "elapsed_seconds": perf_counter() - started, "cost_usd": 0}


def cases(split):
    if split == "dev":
        rows = read(DEV)
        if (sum(row["group"] != "missing" for row in rows) < 15
                or sum(row["group"] == "missing" for row in rows) < 3):
            raise ValueError("Incomplete dev coverage")
        return rows
    rows = read(TEST)
    required = {"table": 6, "image": 5, "chart": 5, "multi": 4, "text": 4, "missing": 6}
    previous = [row for path in (ROOT / "data").glob("bonus*test.json") if path != TEST for row in read(path)]
    past_questions = {SCOPED.key(row["question"]) for row in [*cases("dev"), *previous]}
    if (Counter(row["group"] for row in rows) != required or len({row["id"] for row in rows}) != 30
            or any(row["split"] != "test" or SCOPED.key(row["question"]) in past_questions for row in rows)):
        raise ValueError("Invalid independent test")
    for row in rows:
        if row["group"] == "multi" and (not CHAIN.fullmatch(row["question"]) or not row.get("bridge")
                or len({ref["page"] for ref in row["evidence"]}) < 2):
            raise ValueError(f"Incomplete chain evidence: {row['id']}")
    return rows


def identity(args):
    return {**passages.fingerprint(args, "test"), "joined_code_sha256": digest(Path(__file__)),
            "joined_dev_sha256": digest(DEV), "joined_test_sha256": digest(TEST), "configs": list(CONFIGS)}


def chain_recorded(trace, bridge):
    events = trace["events"]
    names = [entry["event"] for entry in events]
    steps = ["hop_search_1", "hop_bind", "hop_search_2", "hop_read_cell"]
    if not all(names.count(step) == 1 for step in steps):
        return False
    positions = [names.index(step) for step in steps]
    if positions != sorted(positions):
        return False
    first, bind, search, cell = (events[i] for i in positions)
    sources = {row["id"] for row in trace["citations"]}
    return (SCOPED.key(bind["value"]) == SCOPED.key(cell["entity"]) == SCOPED.key(bridge["entity"])
            and SCOPED.contains(bind["next_query"], bind["value"])
            and not SCOPED.contains(trace["question"], bind["value"])
            and bind["next_query"] == search["query"]
            and {bind["source_id"], cell["source_id"]} == sources
            and any(row["id"] == bind["source_id"] for row in first["candidates"])
            and any(row["id"] == cell["source_id"] for row in search["candidates"]))


def score(trace_path, review_path, rows):
    review, traces = read(review_path), read(trace_path)
    if review["trace_sha256"] != digest(trace_path):
        raise ValueError("Review must match the trace")
    groups = {}
    chains = 0
    for case, trace, label in zip(rows, traces, review["labels"], strict=True):
        if not case["id"] == trace["id"] == label["id"] or type(label["passed"]) is not bool or not label["reason"]:
            raise ValueError("Missing or invalid review entry")
        expected = "abstain" if case["group"] == "missing" else "answered"
        if label["passed"] and trace["status"] != expected:
            raise ValueError("Review passed an invalid response status")
        group = groups.setdefault(case["group"], {"passed": 0, "total": 0})
        group["total"] += 1
        group["passed"] += label["passed"]
        if label["passed"] and case.get("bridge"):
            chains += chain_recorded(trace, case["bridge"])
    times = [row["elapsed_seconds"] for row in traces]
    passed = sum(group["passed"] for group in groups.values())
    return {"passed": passed, "total": len(traces), "rate": passed / len(traces), "by_group": groups,
            "verified_chains": chains, "chain_cases": sum(bool(case.get("bridge")) for case in rows),
            "errors": sum(row["status"] == "error" for row in traces), "median_seconds": median(times),
            "total_seconds": sum(times), "cost_usd": sum(row["cost_usd"] for row in traces),
            "trace_sha256": digest(trace_path), "review_sha256": digest(review_path)}


def reviewed_dev(folder):
    files, metrics = {}, {}
    for config in CONFIGS:
        names = [f"{config}.json", f"{config}.review.json", f"{config}.summary.json"]
        trace, review, summary = (folder / name for name in names)
        data = score(trace, review, cases("dev"))
        if data != read(summary):
            raise ValueError(f"Dev summary is stale for {config}")
        files.update({name: digest(folder / name) for name in names})
        metrics[config] = data
    return files, metrics


def choose(metrics):
    eligible = [name for name in CONFIGS if metrics[name]["verified_chains"] == metrics[name]["chain_cases"]]
    if not eligible:
        raise ValueError("No configuration passed all dependent dev chains")
    return max(eligible, key=lambda name: (metrics[name]["passed"],
               metrics[name]["by_group"]["multi"]["passed"], -metrics[name]["errors"], -metrics[name]["median_seconds"]))


def verify_freeze(output, current):
    record = read(output / "selection.json")
    dev = output / "dev"
    hashes, metrics = reviewed_dev(dev)
    if (record["identity"] != current or read(dev / "fingerprint.json") != current
            or record["dev_files"] != hashes or record["dev_metrics"] != metrics or record["selected"] != choose(metrics)):
        raise ValueError("Frozen configuration or reviewed dev evidence changed")
    return record


def run(args, split, configs, current):
    public, local = args.output / split, args.full / split
    public.mkdir(parents=True, exist_ok=False)
    local.mkdir(parents=True, exist_ok=False)
    index = passages.PassageIndex(args.index, args.embedding, args.pdf)
    for config in configs:
        traces = []
        for case in cases(split):
            row = {"id": case["id"], **respond(case["question"], index, args.endpoint, config)}
            traces.append(row)
            write(local / f"{config}.json", traces)
            write(public / f"{config}.partial.json", shareable(traces))
            print(split, config, row["id"], row["status"], round(row["elapsed_seconds"], 2), flush=True)
        (public / f"{config}.partial.json").replace(public / f"{config}.json")
    write(public / "fingerprint.json", current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("dev", "score-dev", "freeze", "test", "score-test"))
    parser.add_argument("--index", type=Path, default=ROOT / ".local/bonus")
    parser.add_argument("--output", type=Path, default=ROOT / "results/bonus_joined")
    parser.add_argument("--full", type=Path, default=ROOT / ".local/bonus/joined")
    parser.add_argument("--pdf", type=Path, default=ROOT.parent / "phan-doan-2.pdf")
    parser.add_argument("--server", type=Path, default=ROOT / ".local/llama-vulkan/llama-server.exe")
    parser.add_argument("--weights", type=Path, default=ROOT / ".local/qwen3-4b-instruct-2507-q4_k_m.gguf")
    parser.add_argument("--embedding", type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8090")
    args = parser.parse_args()
    selection = args.output / "selection.json"
    dev, test = args.output / "dev", args.output / "test"
    if args.phase == "score-dev":
        if selection.exists():
            raise FileExistsError(selection)
        for config in CONFIGS:
            result = score(dev / f"{config}.json", dev / f"{config}.review.json", cases("dev"))
            write(dev / f"{config}.summary.json", result)
            print(config, result)
        return
    if args.phase == "score-test":
        record = verify_freeze(args.output, read(test / "fingerprint.json"))
        config = record["selected"]
        result = score(test / f"{config}.json", test / f"{config}.review.json", cases("test"))
        if result["verified_chains"] != result["by_group"]["multi"]["passed"]:
            raise ValueError("A passing multi-hop response lacks its dependent retrieval trace")
        write(test / "summary.json", result)
        print(result)
        return
    if not args.embedding or sha(args.pdf) != SOURCE_SHA:
        parser.error("Expected the assigned PDF and --embedding")
    cases("test")
    current = identity(args)
    if args.phase == "dev":
        run(args, "dev", CONFIGS, current)
    elif args.phase == "freeze":
        if selection.exists():
            raise FileExistsError(selection)
        hashes, metrics = reviewed_dev(dev)
        if read(dev / "fingerprint.json") != current:
            raise ValueError("Dev pipeline differs from freeze")
        write(selection, {"identity": current, "selected": choose(metrics), "dev_files": hashes,
                          "dev_metrics": metrics, "frozen_at": datetime.now(timezone.utc).isoformat(),
                          "criterion": "All dev chains verified, then dev passes, multi-hop passes, fewer errors, lower median latency"})
    else:
        record = verify_freeze(args.output, current)
        run(args, "test", [record["selected"]], current)


if __name__ == "__main__":
    main()

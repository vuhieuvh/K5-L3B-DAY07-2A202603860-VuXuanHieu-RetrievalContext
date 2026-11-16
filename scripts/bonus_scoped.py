"""Run a bonus evaluation with explicit source, dimension, and sequence constraints."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter

from scripts import bonus_verified as previous
from bonus.ingest import ROOT, SOURCE_SHA, sha
from bonus.benchmark import complete
from src.agent import action_variant
from src.benchmark import digest, read, shareable, write


TEST = ROOT / "data/bonus_scoped_test.json"
key = previous.key
contains = previous.contains
REFUSAL = previous.REFUSAL
DIMENSIONS = (
    (r"\bkva\b", r"\bkva\b"),
    (r"\bkw\b", r"\bkw\b"),
    (r"\bkv\b|dien ap", r"\bkv\b|dien ap"),
    (r"mat do dan so|nguoi (?:tren )?km2", r"mat do dan so|nguoi (?:tren )?km2"),
    (r"suc chua|bao nhieu (?:cho|o to)", r"suc chua|so cho|so xe"),
    (r"gia (?:mua|ban|dien|dat)|dong kwh", r"gia (?:mua|ban|dien|dat)|dong kwh"),
    (r"toa do|\bgps\b", r"toa do|\bgps\b"),
    (r"nam xay dung|nam hoan thanh|xay vao nam", r"nam xay dung|nam hoan thanh"),
    (r"\b(hang san xuat|thuong hieu|tai trong|nang suat|gioi tinh|dan so nam|dan so nu|nhom tuoi|ho gia dinh)\b", None),
)


def missing_dimension(question, hits):
    query = key(question.replace("²", "2"))
    for request, support in DIMENSIONS:
        match = re.search(request, query)
        if not match:
            continue
        if not any(re.search(support or rf"\b{match[0]}\b", key(row["text"].replace("²", "2")))
                   for row in hits):
            return match[0]
    return None


def section_name(question):
    match = re.search(r"\bmục\s+([^,?;]+)[,;]", question, re.IGNORECASE)
    return match[1].strip() if match else ""


def scope_hits(index, question, theme):
    hits, route = index.candidates(question, theme)
    if route != "text":
        return hits, route
    section = section_name(question)
    if section:
        headings = [row for row in index.rows if row["kind"] == "text"
                    and any(contains(line[:175], section) for line in row["text"].splitlines())]
        if headings:
            # Headings can share a chunk with their first paragraphs. Admit
            # the next native chunk only when it is on the same source page.
            requested = {r["id"] for r in headings}
            adjacent = {i + 1 for i, row in enumerate(index.rows[:-1])
                        if row["id"] in requested and row["page"] == index.rows[i + 1]["page"]
                        and index.rows[i + 1]["kind"] == "text"}
            return [*headings, *(index.rows[i] for i in sorted(adjacent))][:5], "section"
    return hits, route


def ordered_value(question, hits):
    pattern = re.compile(r"\bngay sau (.+?) va (?:ngay )?truoc (.+?)(?: la gi|\s*$)")
    query = key(question)
    bracket = pattern.search(query) or re.search(r"\bngay giua (.+?) va (.+?)\s*$", query)
    if not bracket:
        return None
    first, last = bracket.groups()
    for row in hits:
        for line in row["text"].splitlines():
            for segment in re.split(r"\.\s+(?=[A-ZÀ-Ỹ])", line):
                if "→" in segment:
                    items = segment.partition(":")[2].strip().rstrip(".").split(" → ")
                elif "từ trái sang phải:" in segment:
                    items = segment.split("từ trái sang phải:", 1)[1].rstrip(".").split(",")
                else:
                    continue
                items = [item.strip() for item in items]
                for i, (left, value, right) in enumerate(zip(items, items[1:], items[2:])):
                    if contains(left, first) and contains(right, last):
                        return value, row, {"event": "read_sequence", "position": i + 2, "items": items}
    return None


def resolve(question, theme, index, endpoint):
    hits, route = scope_hits(index, question, theme)
    if route == "figure" and not re.search(r"\b(ten hinh|tieu de|chu thich)\b", key(question)):
        hits = [{**row, "text": row["text"].partition("\n")[2] or row["text"]} for row in hits]
    events = [{"event": "search", "query": question, "route": route, "candidates": hits}]
    if not hits:
        return REFUSAL, [], events
    missing = missing_dimension(question, hits)
    if missing:
        return REFUSAL, [], [*events, {"event": "reject", "reason": "dimension_absent", "dimension": missing}]
    if order := ordered_value(question, hits):
        answer, row, step = order
        return answer, [row], [*events, step]
    if route == "grid" and (cell := previous.direct_grid(question, hits)):
        answer, row, field = cell
        return answer, [row], [*events, {"event": "read_cell", "field": field, "id": row["id"]}]
    if route == "chart":
        answer, step = previous.chart_answer(question, hits[0], endpoint)
        events.append(step)
        if answer is not None:
            return answer, [hits[0]] if answer != REFUSAL else [], events
    refs = {f"S{i}": row for i, row in enumerate(hits, 1)}
    string = {"type": "string", "minLength": 1}
    schema = {"oneOf": [action_variant("abstain"), action_variant(
        "answer", answer=string, source={"enum": list(refs)}, quote=string)]}
    prompt = previous.SYSTEM + "\nNếu hỏi đối tượng sau hoặc trước trong chuỗi, hãy đếm đúng bước."
    payload = json.dumps({"question": question, "theme": theme,
                          "sources": {name: row["text"] for name, row in refs.items()}}, ensure_ascii=False)
    action, usage = complete(endpoint, prompt, payload, schema, 190)
    events.append({"event": "model", "proposal": action, "usage": usage})
    if action["action"] == "answer":
        row = refs[action["source"]]
        answer = action["answer"].strip()
        quote = action["quote"]
        is_refusal = re.match(r"(?:khong (?:co thong tin|du (?:thong tin|bang chung)|tim thay)|chua co thong tin)\b", key(answer))
        if (not is_refusal and key(quote) and contains(row["text"], quote)
                and all(contains(row["text"], subject) for subject in previous.explicit_subjects(question))
                and not missing_dimension(question, [row])):
            return answer, [row], events
        events.append({"event": "reject", "reason": "quote_subject_or_dimension_unverified"})
    return REFUSAL, [], events


def respond(question, index, endpoint):
    started = perf_counter()
    parts = re.split(r"\s*\(\d+\)\s*", question)
    theme, questions = (parts[0], parts[1:]) if len(parts) > 2 else ("", [question])
    answers, citations, events = [], [], []
    status = "answered"
    try:
        for part in questions:
            answer, sources, steps = resolve(part, theme, index, endpoint)
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
            "answer": " ".join(answers) if status == "answered" else REFUSAL,
            "citations": citations if status == "answered" else [],
            "elapsed_seconds": perf_counter() - started, "cost_usd": 0}


def cases(split):
    if split == "dev":
        diagnostics = {"D09", "D10", "D16", "R24", "R30", "RN20", "RN25"}
        old_failures = {"V09", "V17", "V23", "V24", "V25", "V26", "V29"}
        return ([row for row in previous.cases_for("dev") if row["id"].startswith("D") or row["id"] in diagnostics]
                + [{**row, "id": "R" + row["id"], "split": "dev"}
                   for row in previous.cases_for("test") if row["id"] in old_failures])
    rows = read(TEST)
    distribution = {"table": 6, "image": 5, "chart": 5, "multi": 4, "text": 4, "missing": 6}
    past = previous.cases_for("dev") + previous.cases_for("test") + previous.benchmark("test") + previous.split_cases("test")
    if (Counter(row["group"] for row in rows) != distribution
            or len({row["id"] for row in rows}) != len(rows)
            or any(row["split"] != "test" for row in rows)
            or {key(row["question"]) for row in rows} & {key(row["question"]) for row in past}):
        raise ValueError("Invalid fresh test")
    return rows


def fingerprint(args, split):
    base = previous.pipeline_identity(args)
    base.update(scoped_source_sha256=digest(Path(__file__)), earlier_test_sha256=digest(previous.TEST))
    return {**base, "scoped_test_sha256": digest(TEST)} if split == "test" else base


def score(folder):
    path = folder / "test/scoped.json"
    review_path = path.with_name("scoped.review.json")
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
        group["total"] += 1
        group["passed"] += label["passed"]
    passed = sum(g["passed"] for g in groups.values())
    times = [row["elapsed_seconds"] for row in traces]
    summary = {"passed": passed, "total": len(traces), "rate": passed / len(traces), "by_group": groups,
               "errors": sum(row["status"] == "error" for row in traces), "median_seconds": median(times),
               "total_seconds": sum(times), "cost_usd": sum(row["cost_usd"] for row in traces),
               "trace_sha256": digest(path), "review_sha256": digest(review_path)}
    write(path.with_name("summary.json"), summary)
    print(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("dev", "freeze", "test", "score-test"))
    parser.add_argument("--index", type=Path, default=ROOT / ".local/bonus")
    parser.add_argument("--output", type=Path, default=ROOT / "results/bonus_scoped")
    parser.add_argument("--full", type=Path, default=ROOT / ".local/bonus/scoped")
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
        write(selection, {"identity": fingerprint(args, "test"), "dev_trace_sha256": digest(dev / "scoped.json")})
        return
    split = args.phase
    identity = fingerprint(args, split)
    if split == "test" and identity != read(selection)["identity"]:
        raise ValueError("Test identity differs from freeze")
    public = args.output / split
    local = args.full / split
    public.mkdir(parents=True, exist_ok=False)
    local.mkdir(parents=True, exist_ok=False)
    index = previous.EvidenceIndex(args.index, args.embedding, args.pdf)
    rows = []
    for case in cases(split):
        row = {"id": case["id"], **respond(case["question"], index, args.endpoint)}
        rows.append(row)
        write(local / "scoped.json", rows)
        write(public / "scoped.partial.json", shareable(rows))
        print(split, row["id"], row["status"], round(row["elapsed_seconds"], 2), flush=True)
    (public / "scoped.partial.json").replace(public / "scoped.json")
    write(public / "fingerprint.json", identity)


if __name__ == "__main__":
    main()

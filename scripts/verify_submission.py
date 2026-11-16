"""Verify the frozen submission and restore its trace text from the Day 6 PDF."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from src.benchmark import (
    ROOT, case_path, digest, evidence_hits, load_cases, read, shareable, summarize, write,
)
from starter.agent_metrics import aggregate


def check(condition, message):
    if not condition:
        raise ValueError(message)


def source_pages(day6):
    sys.path.insert(0, str(day6))
    from starter.src.ingestion import load_pdf

    manifest = read(day6 / "data/manifest.json")
    pdf = day6 / ".local/3626-text.pdf"
    check(digest(pdf, binary=True) == manifest["sha256"], "Day 6 PDF digest mismatch")
    return load_pdf(pdf, manifest["source_id"], manifest["source_path_or_url"])


def restore(trace, pages):
    agent = trace["agent"]
    searches = [event for event in agent["events"] if event["event"] == "search"]
    ranked_lists = [trace["original_query_results"], agent["context_chunks"]]
    ranked_lists.extend(event.get("results", []) for event in searches)
    ranked_lists.extend(event.get("context_candidates", []) for event in searches)
    chunks = {}
    for ranked in ranked_lists:
        for chunk in ranked:
            page = pages[chunk["page"] - 1]
            start, end = (chunk["metadata"][key] for key in ("start", "end"))
            check(
                page.document_id == chunk["source_id"] and page.source == chunk["source"]
                and 0 <= start < end <= len(page.text),
                f"Invalid source or span for {chunk['id']}",
            )
            chunk["text"] = page.text[start:end]
            chunks[chunk["id"]] = chunk

    def restore_context(blocks, ids):
        for block, cid in zip(blocks, ids, strict=True):
            chunk = chunks[cid]
            check(
                (block["source"], block["page"], block["article"])
                == (chunk["source_id"], chunk["page"], chunk["metadata"]["article"]),
                f"Context provenance mismatch for {cid}",
            )
            block["text"] = chunk["text"]

    for event in searches:
        if "context" in event:
            restore_context(event["context"], event["context_ids"])
    final_ids = [agent["context_label_to_id"][block["label"]] for block in agent["context"]]
    check(final_ids == [chunk["id"] for chunk in agent["context_chunks"]],
          f"{trace['query_id']}: context order mismatch")
    restore_context(agent["context"], final_ids)
    check(set(agent["citations"]) <= set(final_ids), f"{trace['query_id']}: citation outside context")
    return set(chunks)


def verify_trial(split, name, summary, review, binding, pages, export, suite="original"):
    cases = load_cases(split, suite)
    folder = ROOT / "results" / ("basic_revised" if suite == "revised" else "") / split
    path = folder / f"{name}.json"
    label_path = ROOT / "reviews" / ("basic_revised" if suite == "revised" else "") / f"{split}_{name}.json"
    check(digest(path) == binding["trace_sha256"] and digest(label_path) == binding["review_sha256"],
          f"{split}/{name}: archived trace or label changed")
    traces = read(path)
    check([(row["query_id"], row["question"]) for row in traces]
          == [(case["id"], case["question"]) for case in cases],
          f"{split}/{name}: questions differ")
    source_ids, complete_top3, answerable = set(), 0, 0
    for row, case in zip(traces, cases, strict=True):
        source_ids.update(restore(row, pages))
        if not case["answerable"]:
            check(all(row[key] is None for key in ("hit1", "hit3", "final_context_has_all_evidence")),
                  f"{case['id']}: missing-evidence case included in ranking")
            continue
        top = row["original_query_results"]
        top3 = evidence_hits(top[:3], case)
        complete_top3 += all(top3)
        answerable += 1
        check(row["hit1"] == any(evidence_hits(top[:1], case)) and row["hit3"] == any(top3)
              and row["final_context_has_all_evidence"]
              == all(evidence_hits(row["agent"]["context_chunks"], case)),
              f"{case['id']}: evidence scores differ")

    recalculated = json.loads(json.dumps(summarize(traces, True)))
    check(all(summary[key] == value for key, value in recalculated.items()),
          f"{split}/{name}: run summary differs")
    labels = read(label_path)
    if suite == "revised":
        check(labels["trace_sha256"] == binding["trace_sha256"], f"{split}/{name}: stale labels")
        labels = labels["reviews"]
    agents = [dict(row["agent"], query_id=row["query_id"]) for row in traces]
    scored = aggregate(cases, agents, labels)
    check(all(review[key] == value for key, value in scored.items()) and review["measured"] == summary,
          f"{split}/{name}: review summary differs")
    grades = Counter(str(row["context_grade"]) for row in labels if "context_grade" in row)
    check(review["context_grades"] == {str(i): grades[str(i)] for i in range(3)},
          f"{split}/{name}: context grades differ")
    check(shareable(traces) == read(path), f"{split}/{name}: compact trace differs")
    if export:
        write(export / split / f"{name}.json", traces)
    print(f"{split}/{name}: {len(traces)} traces, all evidence groups in top 3: "
          f"{complete_top3}/{answerable}")
    return len(traces), source_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6", type=Path, required=True)
    parser.add_argument("--export", type=Path, help="Directory for reconstructed full traces")
    parser.add_argument("--suite", choices=("original", "revised"), default="original")
    args = parser.parse_args()
    if args.export:
        destination = args.export.resolve()
        protected = ROOT / "results"
        check(destination != protected and protected not in destination.parents,
              "Export must use a directory outside the shared results")
    pages = source_pages(args.day6.resolve())
    root = ROOT / "results" / ("basic_revised" if args.suite == "revised" else "")
    selection = read(root / "selection.json")
    archive = ROOT / "results/frozen_protocol"
    bindings = read(archive / "trace_review_bindings.json") if args.suite == "original" else None
    identity = selection["identity"]
    check(digest(root / "dev/review_summary.json") == selection["dev_review_sha256"],
          "Dev review differs from frozen selection")
    for path, sha in identity["pipeline"].items():
        recorded = (archive / Path(path).name if args.suite == "original"
                    and path in ("src/agent.py", "src/benchmark.py", "src/retrieval.py")
                    else ROOT / path)
        check(digest(recorded) == sha, f"Frozen pipeline differs: {path}")

    total, chunks = 0, set()
    for split in ("dev", "test"):
        folder = root / split
        run = read(folder / "summary.json")
        review = read(folder / "review_summary.json")
        check(run["identity"] == identity, f"{split}: experiment identity differs")
        expected = set(identity["configs"]) if split == "dev" else {
            selection["selected"], selection["baseline"],
        }
        check(set(run["results"]) == set(review) == expected, f"{split}: missing or extra trials")
        check(digest(case_path(split, args.suite)) == identity[f"benchmark_{split}_sha256"],
              f"{split}: benchmark digest mismatch")
        for name, summary in run["results"].items():
            count, ids = verify_trial(
                split, name, summary, review[name],
                bindings[f"{split}/{name}"] if bindings is not None else review[name]["binding"],
                pages, args.export, args.suite,
            )
            total += count
            chunks.update(ids)
    print(f"Verified {total} traces and {len(chunks)} source chunks.")


if __name__ == "__main__":
    main()

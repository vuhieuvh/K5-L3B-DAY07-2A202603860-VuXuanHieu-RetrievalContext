"""Inspect bonus evidence regions and verify a stored bonus benchmark."""
import argparse
import re
from pathlib import Path

import fitz

from bonus.benchmark import benchmark, evaluate_labels
from bonus.ingest import ROOT, SOURCE_SHA, sha
from src.benchmark import digest, read, shareable, write


def regions(document, load_cases=benchmark):
    for split in ("dev", "test"):
        for case in load_cases(split):
            for region in case.get("evidence", case.get("checked_regions", [])):
                number = region["page"]
                box = fitz.Rect(region["bbox"])
                if not 1 <= number <= len(document) or box.is_empty:
                    raise ValueError(f"Invalid page or region: {case['id']}")
                if not (document[number - 1].rect + (-1, -1, 1, 1)).contains(box):
                    raise ValueError(f"Region outside source page: {case['id']}")
                yield case["id"], number, box


def prepare_review(output, split, name):
    path = output / split / f"{name}.json"
    target = output / split / f"{name}.review.json"
    if target.exists():
        raise FileExistsError(target)
    write(target, {
        "trace_sha256": digest(path),
        "labels": [{"id": trace["id"], "passed": None, "reason": ""} for trace in read(path)],
    })


def verify_run(output):
    record = read(output / "selection.json")
    for path, expected in record["identity"]["inputs"].items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Frozen file changed: {path}")
    for name, summary in record["dev"].items():
        if evaluate_labels(output, "dev", name) != summary:
            raise ValueError(f"Stored dev result differs: {name}")
    chosen = record["selected"]
    if read(output / "test" / f"{chosen}.identity.json") != record["identity"]:
        raise ValueError("Test used a different pipeline from the freeze")
    final = evaluate_labels(output, "test", chosen)
    if read(output / "test/summary.json") != final:
        raise ValueError("Stored test summary differs from trace and labels")
    print(f"Verified {final['passed']}/{final['total']} on test ({100*final['rate']:.2f}%).")


def restore_test(output, index, destination):
    selection = read(output / "selection.json")
    index_file = index / "chunks.json"
    if sha(index_file) != selection["identity"]["chunks_sha256"]:
        raise ValueError("The chunk index differs from the frozen run")
    name = selection.get("selected", "refined")
    source = output / "test" / f"{name}.json"
    chunks = {chunk["id"]: chunk for chunk in read(index_file)}
    rows = read(source)
    for row in rows:
        for label, cid in row["context_ids"].items():
            chunk = chunks[cid]
            context = row["context"][label]
            if any(context[key] != chunk[key] for key in ("page", "kind")):
                raise ValueError(f"Context source differs for {row['id']}/{label}")
            context["text"] = chunk["text"]
        for event in row["events"]:
            for result in event.get("results", []):
                result["text"] = chunks[result["id"]]["text"]
        for citation in row["citations"]:
            citation["text"] = chunks[citation["id"]]["text"]
    if shareable(rows) != read(source):
        raise ValueError("Restored trace differs from shared trace")
    target = destination / f"{name}.json"
    if target.exists():
        raise FileExistsError(target)
    write(target, rows)
    print(f"Restored {len(rows)} full test traces: {target}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "results/bonus")
    parser.add_argument("--case", help="Evidence ID to render, for example T15")
    parser.add_argument("--crop", type=Path, help="Directory for local evidence PNGs")
    parser.add_argument("--prepare-review", nargs=2, metavar=("SPLIT", "CONFIG"))
    parser.add_argument("--verify-run", action="store_true")
    parser.add_argument("--refined", action="store_true", help="Use the second, independent evaluation split")
    parser.add_argument("--index", type=Path, default=ROOT / ".local/bonus")
    parser.add_argument("--restore", type=Path, help="Directory for reconstructed full test trace")
    args = parser.parse_args()
    if args.prepare_review:
        split, name = args.prepare_review
        if split not in ("dev", "test") or not re.fullmatch(r"[a-z_]+", name):
            parser.error("Invalid split or configuration")
        prepare_review(args.output, split, name)
        return
    if not args.pdf:
        parser.error("--pdf is required for source verification")
    if args.crop and not args.case:
        parser.error("--crop requires --case")
    if sha(args.pdf) != SOURCE_SHA:
        raise ValueError("Unexpected source document SHA-256")
    load_cases = benchmark
    if args.refined:
        from scripts.bonus_refined import score, split_cases

        load_cases = split_cases
    with fitz.open(args.pdf) as document:
        references = list(regions(document, load_cases))
        print(f"Checked {len(document)} pages and {len(references)} benchmark source regions.")
        if args.case:
            selected = [item for item in references if item[0] == args.case.upper()]
            if not selected:
                raise ValueError("Unknown case")
            for i, (cid, number, box) in enumerate(selected, 1):
                print(cid, number, tuple(box))
                if args.crop:
                    args.crop.mkdir(parents=True, exist_ok=True)
                    out = args.crop / f"{cid}-{i}-page-{number}.png"
                    document[number - 1].get_pixmap(
                        matrix=fitz.Matrix(2, 2), clip=box, alpha=False,
                    ).save(out)
    if args.verify_run:
        if args.refined:
            record = read(args.output / "selection.json")
            for path, expected in record["identity"]["inputs"].items():
                if digest(ROOT / path) != expected:
                    raise ValueError(f"Frozen file changed: {path}")
            for file, key in (("scripts/bonus_refined.py", "refined_source_sha256"),
                              ("data/bonus_refined_test.json", "fresh_test_sha256")):
                if digest(ROOT / file) != record["identity"][key]:
                    raise ValueError(f"Frozen file changed: {file}")
            if score(args.output, "dev") != record["dev"]:
                raise ValueError("Stored refined dev review differs")
            if read(args.output / "test/fingerprint.json") != record["identity"]:
                raise ValueError("Refined test identity differs")
            result = score(args.output, "test")
            if result != read(args.output / "test/summary.json"):
                raise ValueError("Stored refined test summary differs")
            print(f"Verified refined test: {result['passed']}/{result['total']}.")
        else:
            verify_run(args.output)
    if args.restore:
        restore_test(args.output, args.index, args.restore)


if __name__ == "__main__":
    main()

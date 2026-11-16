"""Build and query an independent hybrid index for the planning PDF."""
import argparse
import re
import unicodedata
from pathlib import Path
from time import perf_counter

import numpy as np
from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType

from bonus.ingest import ROOT, sha
from src.benchmark import read, write
from src.retrieval import EMBEDDING, WEIGHTS
from starter.baseline import TfidfIndex


def normalize(text):
    decomposed = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def lexical_key(text):
    words = re.findall(r"\w+", normalize(text))
    return " ".join(words + ["_".join(words[i:i+size]) for size in (2, 3)
                             for i in range(len(words)-size+1)])


def embedder(model):
    if EMBEDDING not in {row["model"] for row in TextEmbedding.list_supported_models()}:
        TextEmbedding.add_custom_model(
            model=EMBEDDING, pooling=PoolingType.MEAN, normalization=True,
            sources=ModelSource(hf=EMBEDDING), dim=384, model_file=WEIGHTS,
        )
    return TextEmbedding(model_name=EMBEDDING, specific_model_path=str(model), threads=4)


def build(folder, model):
    source = folder / "extracted.json"
    visuals = ROOT / "data/bonus_visuals.json"
    snapshot = read(source)
    chunks = snapshot["chunks"] + [
        {**card, "text": card["title"] + "\n" + card["text"]} for card in read(visuals)
    ]
    counter = {}
    for chunk in chunks:
        key = (chunk["page"], chunk["kind"])
        counter[key] = counter.get(key, 0) + 1
        chunk["id"] = f"P{key[0]:03d}-{key[1]}-{counter[key]:02d}"
    started = perf_counter()
    vectors = np.stack(list(embedder(model).embed(
        ["passage: " + chunk["text"] for chunk in chunks], batch_size=16,
    ))).astype(np.float32)
    np.save(folder / "vectors.npy", vectors, allow_pickle=False)
    write(folder / "chunks.json", chunks)
    profile = {
        "pdf_pages": len(snapshot["pages"]),
        "indexed_pages": len({chunk["page"] for chunk in chunks}),
        "chunks": len(chunks),
        "chunks_by_type": {kind: sum(c["kind"] == kind for c in chunks)
                           for kind in sorted({c["kind"] for c in chunks})},
        "pages": snapshot["pages"],
        "unindexed_pages": sorted({row["page"] for row in snapshot["pages"]}
                                  - {chunk["page"] for chunk in chunks}),
        "embedding": EMBEDDING,
        "embedding_weights_sha256": sha(model / WEIGHTS),
        "embedding_dimensions": int(vectors.shape[1]),
        "build_seconds": perf_counter() - started,
        "build_service_cost_usd": 0,
    }
    write(folder / "index_profile.json", profile)
    print(profile["chunks_by_type"], profile["indexed_pages"], round(profile["build_seconds"], 2))
    return profile


def scope(query, rows):
    key = normalize(query)
    figure = re.search(r"\bhinh\s+(\d+)\b", key)
    if figure:
        pattern = rf"^hinh {figure[1]}\b"
        matches = [i for i, chunk in enumerate(rows)
                   if re.search(pattern, normalize(chunk.get("title", "")))]
        if matches:
            return matches
    if "bieu do" in key:
        return [i for i, chunk in enumerate(rows) if chunk["kind"] == "chart"]
    if re.search(r"\bbang (?!bao\b|chung\b)", key):
        matches = [i for i, chunk in enumerate(rows) if chunk["kind"] == "table"]
        if matches:
            return matches
    return list(range(len(rows)))


class Index:
    def __init__(self, folder, model):
        self.rows = read(folder / "chunks.json")
        self.vector = np.load(folder / "vectors.npy", allow_pickle=False)
        self.encoder = embedder(model)
        self.lookup = {chunk["id"]: i for i, chunk in enumerate(self.rows)}
        self.lexical = TfidfIndex([{"id": c["id"], "text": lexical_key(c["text"])}
                                  for c in self.rows])

    def search(self, query, *, routed, limit):
        allowed = scope(query, self.rows) if routed else list(range(len(self.rows)))
        if not allowed:
            return []
        permitted = set(allowed)
        lexical = self.lexical.search(lexical_key(query), len(self.rows))
        lex = [self.lookup[r["id"]] for r in lexical if self.lookup[r["id"]] in permitted]
        vector = next(self.encoder.embed(["query: " + query]))
        similarity = self.vector @ vector
        semantic = sorted(allowed, key=lambda pos: (-float(similarity[pos]), pos))
        scores = dict.fromkeys((*lex[:30], *semantic[:30]), 0.0)
        for ranked, weight in ((lex, 1.3), (semantic, 1.0)):
            for rank, pos in enumerate(ranked[:30], 1):
                scores[pos] += weight / (12 + rank)
        return [{**self.rows[pos], "score": score}
                for pos, score in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=ROOT / ".local/bonus")
    parser.add_argument("--embedding", type=Path, required=True)
    options = parser.parse_args()
    build(options.folder, options.embedding)

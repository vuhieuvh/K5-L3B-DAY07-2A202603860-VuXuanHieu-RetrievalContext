"""Read the frozen Day 6 Qdrant index and rank the same corpus three ways."""
from pathlib import Path

from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from onnxruntime.capi import onnxruntime_pybind11_state as ort
from qdrant_client import QdrantClient, models

from starter.baseline import TfidfIndex

EMBEDDING = "intfloat/multilingual-e5-small"
WEIGHTS = "onnx/model_qint8_avx512_vnni.onnx"
COLLECTION = "structured"


class EmbeddingError(RuntimeError):
    """The embedding backend failed to produce a query vector."""


def unpack(point):
    payload = point.payload
    return {
        "id": str(point.id),
        "source_id": payload["document_id"],
        "source": payload["source"],
        "page": payload["page"],
        "text": payload["text"],
        "metadata": {key: payload[key] for key in ("chapter", "article", "start", "end")},
    }


class Retrieval:
    def __init__(self, index_path: Path, model_path: Path):
        if not (index_path / "collection" / COLLECTION / "storage.sqlite").is_file():
            raise FileNotFoundError(f"Day 6 Qdrant collection not found: {index_path}")
        if not (model_path / WEIGHTS).is_file():
            raise FileNotFoundError(f"Day 6 embedding weights not found: {model_path}")
        if EMBEDDING not in {row["model"] for row in TextEmbedding.list_supported_models()}:
            TextEmbedding.add_custom_model(
                model=EMBEDDING, pooling=PoolingType.MEAN, normalization=True,
                sources=ModelSource(hf=EMBEDDING), dim=384, model_file=WEIGHTS,
            )
        self.embedder = TextEmbedding(
            model_name=EMBEDDING, specific_model_path=str(model_path), threads=4,
        )
        self.client = QdrantClient(path=str(index_path))
        try:
            index_config = self.client.get_collection(COLLECTION).config.params.vectors
            if index_config.size != 384 or index_config.distance != models.Distance.COSINE:
                raise ValueError("Day 6 index must use 384-dimensional cosine vectors")
            self.chunks = self._read_chunks()
            self.lexical = TfidfIndex(self.chunks)
        except Exception:
            self.close()
            raise

    def _read_chunks(self):
        chunks, offset = [], None
        while True:
            points, offset = self.client.scroll(
                COLLECTION, offset=offset, limit=128, with_payload=True, with_vectors=False,
            )
            chunks.extend(map(unpack, points))
            if offset is None:
                break
        return sorted(chunks, key=lambda chunk: chunk["id"])

    def search(self, query, method, limit):
        if method == "lexical":
            return self.lexical.search(query, limit)
        if method not in ("dense", "hybrid"):
            raise ValueError(f"Unknown retrieval method: {method}")
        depth = max(10, limit) if method == "hybrid" else limit
        try:
            vector = next(self.embedder.embed(["query: " + query])).tolist()
        except (ort.Fail, ort.RuntimeException, ort.InvalidArgument, ort.EPFail,
                ort.EngineError, ort.DeviceReset, ort.NotImplemented) as error:
            raise EmbeddingError(
                f"ONNX query embedding failed ({type(error).__name__}): {error}"
            ) from error
        points = self.client.query_points(
            COLLECTION, query=vector, limit=depth, with_payload=True,
        ).points
        dense = [{**unpack(point), "score": point.score, "strategy": "dense"} for point in points]
        if method == "dense":
            return dense
        return fuse(dense, self.lexical.search(query, depth), limit)

    def close(self):
        self.client.close()


def fuse(dense, lexical, limit):
    fused = {}
    for method, rows in (("dense", dense), ("lexical", lexical)):
        for rank, chunk in enumerate(rows, 1):
            item = fused.setdefault(chunk["id"], {
                **chunk, "strategy": "hybrid", "score": 0.0, "component_ranks": {},
            })
            item["score"] += 1.0 / (60 + rank)
            item["component_ranks"][method] = rank
    return sorted(fused.values(), key=lambda row: (-row["score"], row["id"]))[:limit]

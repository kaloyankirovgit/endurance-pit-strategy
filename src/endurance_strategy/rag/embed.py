from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from endurance_strategy.rag.retrieve import BM25

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingRetriever:
    """Cosine similarity between a query embedding and chunk embeddings, same interface as BM25.

    Chunk vectors are cached on disk, keyed by model and chunk text, because embedding
    855 chunks on a laptop CPU takes a few minutes.
    """

    def __init__(self, chunks: list[dict], cache_dir: str | Path, model_name: str = DEFAULT_MODEL):
        from fastembed import TextEmbedding

        self.chunks = chunks
        self.model_name = model_name
        self.model = TextEmbedding(model_name)
        key = hashlib.sha256((model_name + json.dumps([c["text"] for c in chunks])).encode()).hexdigest()[:16]
        cache = Path(cache_dir) / f"regulation_embeddings_{key}.npy"
        if cache.exists():
            self.vectors = np.load(cache)
        else:
            self.vectors = self._normalise(np.array(list(self.model.embed([c["text"] for c in chunks]))))
            np.save(cache, self.vectors)

    @staticmethod
    def _normalise(vectors: np.ndarray) -> np.ndarray:
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def search(self, query: str, k: int = 5, season: str | None = None) -> list[tuple[dict, float]]:
        query_vector = self._normalise(np.array(list(self.model.embed([BGE_QUERY_PREFIX + query]))))[0]
        similarities = self.vectors @ query_vector
        candidates = [i for i, c in enumerate(self.chunks) if season is None or c["season"] == season]
        ranked = sorted(candidates, key=lambda i: (-similarities[i], self.chunks[i]["chunk_id"]))
        return [(self.chunks[i], float(similarities[i])) for i in ranked[:k]]


class HybridRetriever:
    """Reciprocal rank fusion of BM25 and embeddings: each list contributes 1 / (60 + rank)."""

    def __init__(self, bm25: BM25, embeddings: EmbeddingRetriever, depth: int = 50, constant: int = 60):
        self.bm25, self.embeddings, self.depth, self.constant = bm25, embeddings, depth, constant

    def search(self, query: str, k: int = 5, season: str | None = None) -> list[tuple[dict, float]]:
        scores: dict[str, float] = {}
        by_id: dict[str, dict] = {}
        for retriever in (self.bm25, self.embeddings):
            for rank, (chunk, _) in enumerate(retriever.search(query, k=self.depth, season=season), start=1):
                scores[chunk["chunk_id"]] = scores.get(chunk["chunk_id"], 0.0) + 1 / (self.constant + rank)
                by_id[chunk["chunk_id"]] = chunk
        ranked = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
        return [(by_id[chunk_id], scores[chunk_id]) for chunk_id in ranked[:k]]

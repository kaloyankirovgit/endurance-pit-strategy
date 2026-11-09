#!/usr/bin/env python3
"""Time BM25 and the hybrid on real questions, for the cost side of the retriever choice (D-027)."""
from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.rag.embed import DEFAULT_MODEL, EmbeddingRetriever, HybridRetriever
from endurance_strategy.rag.retrieve import BM25

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"
QUESTION_FILES = ("questions.json", "questions_heldout.json")
N_QUESTIONS = 40


def timed(function) -> tuple[object, float]:
    start = time.perf_counter()
    value = function()
    return value, time.perf_counter() - start


def main() -> None:
    chunks = [json.loads(line) for line in (INTERIM_DIR / "regulation_chunks.jsonl").read_text().splitlines()]
    questions = [q["question"] for name in QUESTION_FILES for q in json.loads((EVAL_DIR / name).read_text())][:N_QUESTIONS]
    bm25, bm25_build_s = timed(lambda: BM25(chunks))
    embeddings, embedding_load_s = timed(lambda: EmbeddingRetriever(chunks, INTERIM_DIR))
    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "embedding_model": DEFAULT_MODEL,
        "questions": len(questions),
        "bm25_build_s": round(bm25_build_s, 3),
        "embedding_load_with_cached_vectors_s": round(embedding_load_s, 2),
        "query_ms": {},
    }
    for name, retriever in (("bm25", bm25), ("hybrid", HybridRetriever(bm25, embeddings))):
        times_ms = [timed(lambda: retriever.search(question, k=5, season="2026"))[1] * 1000 for question in questions]
        report["query_ms"][name] = {"median": round(statistics.median(times_ms), 1), "max": round(max(times_ms), 1)}
    results = EVAL_DIR / "results"
    (results / f"{report['timestamp_utc']}_cost.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

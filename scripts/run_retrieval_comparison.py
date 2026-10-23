#!/usr/bin/env python3
"""Compare BM25, embeddings and a hybrid on the original and the held-out question sets."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.rag.embed import DEFAULT_MODEL, EmbeddingRetriever, HybridRetriever
from endurance_strategy.rag.evaluate import evaluate
from endurance_strategy.rag.retrieve import BM25

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"
MODEL_TOKEN_LIMIT_WORDS = 380


def main() -> None:
    chunks = [json.loads(line) for line in (INTERIM_DIR / "regulation_chunks.jsonl").read_text().splitlines()]
    question_sets = {
        "original": json.loads((EVAL_DIR / "questions.json").read_text()),
        "heldout": json.loads((EVAL_DIR / "questions_heldout.json").read_text()),
    }
    bm25 = BM25(chunks)
    embeddings = EmbeddingRetriever(chunks, INTERIM_DIR)
    retrievers = {"bm25": bm25, "embeddings": embeddings, "hybrid": HybridRetriever(bm25, embeddings)}

    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "embedding_model": DEFAULT_MODEL,
        "chunks_over_about_512_tokens": sum(len(c["text"].split()) > MODEL_TOKEN_LIMIT_WORDS for c in chunks),
        "chunks": len(chunks),
        "results": {},
    }
    for set_name, questions in question_sets.items():
        for name, retriever in retrievers.items():
            result = evaluate(retriever, questions)
            report["results"][f"{set_name}/{name}"] = result
            print(f"{set_name:9s} {name:10s}", {k: v for k, v in result.items() if k.startswith("recall") or k == "questions"})
    results = EVAL_DIR / "results"
    results.mkdir(exist_ok=True)
    (results / f"{report['timestamp_utc']}_comparison.json").write_text(json.dumps(report, indent=2))
    print("chunks over ~512 tokens:", report["chunks_over_about_512_tokens"], "of", report["chunks"])


if __name__ == "__main__":
    main()

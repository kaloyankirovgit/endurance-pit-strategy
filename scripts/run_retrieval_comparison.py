#!/usr/bin/env python3
"""Compare BM25, embeddings and a hybrid on the original, held-out and vague question sets."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.rag.embed import DEFAULT_MODEL, EmbeddingRetriever, HybridRetriever
from endurance_strategy.rag.evaluate import compare_hits, evaluate, sign_test
from endurance_strategy.rag.retrieve import BM25

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"
MODEL_TOKEN_LIMIT_WORDS = 380


def main() -> None:
    chunks = [json.loads(line) for line in (INTERIM_DIR / "regulation_chunks.jsonl").read_text().splitlines()]
    question_sets = {
        "original": json.loads((EVAL_DIR / "questions.json").read_text()),
        "heldout": json.loads((EVAL_DIR / "questions_heldout.json").read_text()),
        "vague": json.loads((EVAL_DIR / "questions_vague.json").read_text()),
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
    report["paired_top5"] = {}
    for set_name in question_sets:
        for challenger in ("hybrid", "embeddings"):
            pair = compare_hits(report["results"][f"{set_name}/{challenger}"], report["results"][f"{set_name}/bm25"])
            report["paired_top5"][f"{set_name}/{challenger}_vs_bm25"] = pair
            print(f"{set_name:9s} {challenger} vs bm25, top 5:", pair)
    # The E-017 decision rule: hybrid against BM25, pooled over the held-out and vague sets.
    pooled = [report["paired_top5"][f"{s}/hybrid_vs_bm25"] for s in ("heldout", "vague")]
    wins, losses = sum(p["wins"] for p in pooled), sum(p["losses"] for p in pooled)
    report["e017_rule"] = {"vague_wins_exceed_losses": pooled[1]["wins"] > pooled[1]["losses"],
                           "pooled_wins": wins, "pooled_losses": losses, "pooled_sign_test_p": sign_test(wins, losses)}
    print("E-017 rule:", report["e017_rule"])
    results = EVAL_DIR / "results"
    results.mkdir(exist_ok=True)
    (results / f"{report['timestamp_utc']}_comparison.json").write_text(json.dumps(report, indent=2))
    print("chunks over ~512 tokens:", report["chunks_over_about_512_tokens"], "of", report["chunks"])


if __name__ == "__main__":
    main()

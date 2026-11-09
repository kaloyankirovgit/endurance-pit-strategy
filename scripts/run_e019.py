#!/usr/bin/env python3
"""Run E-019: BM25 against the hybrid on the racer agent's questions, under the rule fixed in the experiment log."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.rag.embed import DEFAULT_MODEL, EmbeddingRetriever, HybridRetriever
from endurance_strategy.rag.evaluate import compare_hits, e019_decision, evaluate
from endurance_strategy.rag.retrieve import BM25

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"
EARLIER_RUN = EVAL_DIR / "results" / "20261026T144012Z_comparison.json"
EARLIER_SETS = {"original": "questions.json", "heldout": "questions_heldout.json", "vague": "questions_vague.json"}
CHUNK_SHA_PREFIX = "6e12122e"
FASTEMBED_VERSION = "0.9.0"
MODEL_SNAPSHOT = "aa8f8b06"
KS = (1, 3, 5)


def load_questions(name: str) -> list[dict]:
    return json.loads((EVAL_DIR / name).read_text())


def ranks(result: dict) -> dict:
    return {row["id"]: row["rank"] for row in result["per_question"]}


def distinct_articles(result: dict, baseline: dict, questions: list[dict]) -> dict:
    """Wins and losses at top 5, counting questions that share their gold articles once."""
    gold = {q["id"]: tuple(sorted(q["gold_articles"])) for q in questions}
    hit = lambda rank: rank is not None and rank <= 5
    base = ranks(baseline)
    wins = {gold[r["id"]] for r in result["per_question"] if hit(r["rank"]) and not hit(base[r["id"]])}
    losses = {gold[r["id"]] for r in result["per_question"] if hit(base[r["id"]]) and not hit(r["rank"])}
    return {"wins": len(wins), "losses": len(losses)}


def main() -> None:
    chunk_path = INTERIM_DIR / "regulation_chunks.jsonl"
    digest = hashlib.sha256(chunk_path.read_bytes()).hexdigest()
    if not digest.startswith(CHUNK_SHA_PREFIX):
        raise SystemExit(f"chunk file changed: {digest}")
    if version("fastembed") != FASTEMBED_VERSION:
        raise SystemExit(f"fastembed is {version('fastembed')}, expected {FASTEMBED_VERSION}")

    chunks = [json.loads(line) for line in chunk_path.read_text().splitlines()]
    bm25 = BM25(chunks)
    embeddings = EmbeddingRetriever(chunks, INTERIM_DIR)
    if MODEL_SNAPSHOT not in str(embeddings.model.model._model_dir):
        raise SystemExit(f"embedding snapshot differs: {embeddings.model.model._model_dir}")
    retrievers = {"bm25": bm25, "embeddings": embeddings, "hybrid": HybridRetriever(bm25, embeddings)}

    earlier = json.loads(EARLIER_RUN.read_text())["results"]
    for set_name, file_name in EARLIER_SETS.items():
        for name, retriever in retrievers.items():
            if ranks(evaluate(retriever, load_questions(file_name))) != ranks(earlier[f"{set_name}/{name}"]):
                raise SystemExit(f"{set_name}/{name} does not reproduce {EARLIER_RUN.name}")
    print("earlier rows reproduced")

    questions = load_questions("questions_fresh.json")
    results = {name: evaluate(retriever, questions) for name, retriever in retrievers.items()}
    paired = {f"k{k}": compare_hits(results["hybrid"], results["bm25"], k=k) for k in KS}
    wins, losses = paired["k5"]["wins"], paired["k5"]["losses"]

    by_wording = {}
    for wording in ("racer", "fan"):
        subset = [q for q in questions if q["wording"] == wording]
        part = {name: evaluate(retriever, subset) for name, retriever in retrievers.items()}
        by_wording[wording] = {
            **{name: {key: result[key] for key in ("questions", "recall@1", "recall@3", "recall@5")} for name, result in part.items()},
            "hybrid_vs_bm25_top5": compare_hits(part["hybrid"], part["bm25"]),
        }

    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "embedding_model": DEFAULT_MODEL,
        "chunk_sha256": digest,
        "reproduced": EARLIER_RUN.name,
        "results": results,
        "hybrid_vs_bm25": paired,
        "hybrid_vs_bm25_distinct_articles_top5": distinct_articles(results["hybrid"], results["bm25"], questions),
        "by_wording_descriptive": by_wording,
        "decision": e019_decision(wins, losses),
    }
    (EVAL_DIR / "results" / f"{report['timestamp_utc']}_e019.json").write_text(json.dumps(report, indent=2))
    for name, result in results.items():
        print(f"{name:10s}", {key: result[key] for key in ("questions", "recall@1", "recall@3", "recall@5")})
    print("paired:", paired)
    print("distinct articles:", report["hybrid_vs_bm25_distinct_articles_top5"])
    print("by wording:", json.dumps(by_wording))
    base = ranks(results["bm25"])
    for row in results["hybrid"]["per_question"]:
        if (row["rank"] is not None and row["rank"] <= 5) != (base[row["id"]] is not None and base[row["id"]] <= 5):
            print("differs:", row["id"], "hybrid", row["rank"], "bm25", base[row["id"]])
    print("decision:", report["decision"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Score BM25 retrieval over the chunked sporting regulations against the hand-built question set."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.rag.evaluate import evaluate, season_variants, top_scores
from endurance_strategy.rag.retrieve import BM25

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"


def main() -> None:
    chunks = [json.loads(line) for line in (INTERIM_DIR / "regulation_chunks.jsonl").read_text().splitlines()]
    questions = json.loads((EVAL_DIR / "questions.json").read_text())
    variants = season_variants(questions, chunks, ["2024", "2025"])
    retriever = BM25(chunks)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "chunks": len(chunks),
        "chunks_by_document": {d: sum(c["document_id"] == d for c in chunks) for d in sorted({c["document_id"] for c in chunks})},
        "season_2026": evaluate(retriever, questions),
        "season_variants_2024_2025": evaluate(retriever, variants),
        "all_seasons_no_filter": evaluate(retriever, questions + variants, filter_season=False),
        "top_scores": top_scores(retriever, questions),
    }
    results = EVAL_DIR / "results"
    results.mkdir(exist_ok=True)
    (results / f"{report['timestamp_utc']}_bm25.json").write_text(json.dumps(report, indent=2))
    for name in ("season_2026", "season_variants_2024_2025", "all_seasons_no_filter"):
        print(name, {k: v for k, v in report[name].items() if k != "per_question"})
    print("top_scores", report["top_scores"])


if __name__ == "__main__":
    main()

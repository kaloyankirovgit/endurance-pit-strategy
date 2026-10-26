#!/usr/bin/env python3
"""Route, retrieve, answer and check every question, then score the answers against the labels."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.paths import INTERIM_DIR
from endurance_strategy.rag.answer import CAR_CLASSES, answer_question
from endurance_strategy.rag.evaluate import grade_answer
from endurance_strategy.rag.retrieve import BM25

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"


def summarise(graded: list[dict], routing: list[dict]) -> dict:
    answerable = [g for g in graded if g["answerable"]]
    unanswerable = [g for g in graded if not g["answerable"]]
    hits = [g for g in answerable if g["retrieval_hit"]]
    misses = [g for g in answerable if not g["retrieval_hit"]]
    with_facts = [g for g in answerable if g["key_facts_checked"]]
    return {
        "answerable_runs": len(answerable),
        "answerable_outcomes": dict(Counter(g["outcome"] for g in answerable)),
        "answered_citing_gold": sum(g["cites_gold"] for g in answerable),
        "key_fact_runs": len(with_facts),
        "key_facts_present": sum(g["key_facts_present"] for g in with_facts),
        "wrong_fact_shown_runs": sum(g["wrong_facts_checked"] and g["shown"] for g in answerable),
        "wrong_facts_present": sum(g["wrong_facts_present"] for g in answerable),
        "retrieval_hit_runs": len(hits),
        "retrieval_hit_answered_citing_gold": sum(g["cites_gold"] for g in hits),
        "retrieval_miss_runs": len(misses),
        "retrieval_miss_outcomes": dict(Counter(g["outcome"] for g in misses)),
        "unanswerable_runs": len(unanswerable),
        "unanswerable_nothing_shown": sum(g["nothing_shown"] for g in unanswerable),
        "unanswerable_outcomes": dict(Counter(g["outcome"] for g in unanswerable)),
        "routing_runs": len(routing) or None,
        "routing_correct": sum(r["correct"] for r in routing) if routing else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--questions", default="questions.json", help="question file in evals/regulations")
    parser.add_argument("--routing", default="routing.json", help="routing-case file in evals/regulations")
    parser.add_argument("--no-routing", action="store_true", help="skip the routing cases")
    args = parser.parse_args()

    chunks = [json.loads(line) for line in (INTERIM_DIR / "regulation_chunks.jsonl").read_text().splitlines()]
    questions = json.loads((EVAL_DIR / args.questions).read_text())
    routing_questions = [] if args.no_routing else json.loads((EVAL_DIR / args.routing).read_text())
    unknown = {q.get("car_class") for q in questions} - set(CAR_CLASSES) - {None}
    if unknown:
        raise SystemExit(f"unknown car classes in {args.questions}: {sorted(unknown)}")
    retriever = BM25(chunks)

    jobs = [("question", q, r) for q in questions for r in range(args.repeats)]
    jobs += [("routing", q, r) for q in routing_questions for r in range(args.repeats)]
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as workdir, ThreadPoolExecutor(args.workers) as pool:
        traces = list(pool.map(lambda job: answer_question(job[1]["question"], job[1].get("season", "2026"), retriever, workdir,
                                                           car_class=job[1].get("car_class")), jobs))
    duration_s = round(time.monotonic() - started)

    graded, routing, log = [], [], []
    for (kind, question, repeat), trace in zip(jobs, traces):
        if kind == "question":
            result = grade_answer(trace, question)
            graded.append(result)
        else:
            result = {"id": question["id"], "correct": trace["route"] == question["expected_route"], "route": trace["route"]}
            routing.append(result)
        log.append({"id": question["id"], "repeat": repeat, "trace": trace, "grade": result})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = EVAL_DIR / "results"
    results.mkdir(exist_ok=True)
    (results / f"{stamp}_answers.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in log))
    summary = {"timestamp_utc": stamp, "questions_file": args.questions,
               "routing_file": None if args.no_routing else args.routing, "repeats": args.repeats, "duration_s": duration_s,
               "retriever": "BM25 top 5, season filter",
               "models": sorted({m for t in traces for m in t["models"]}), **summarise(graded, routing)}
    (results / f"{stamp}_answers_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

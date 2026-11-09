#!/usr/bin/env python3
"""Have the blind racer agent write the E-019 questions, and save every question it wrote, in order."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.rag.racer_agent import PERSONAS, ask_persona, leaked_terms, run_canary, select_questions

EVAL_DIR = Path(__file__).resolve().parents[1] / "evals" / "regulations"
OUTPUT_DIR = EVAL_DIR / "racer_agent"
EARLIER_SETS = ("questions.json", "questions_heldout.json", "questions_vague.json")


def earlier_answerable() -> list[str]:
    return [q["question"] for name in EARLIER_SETS for q in json.loads((EVAL_DIR / name).read_text()) if q["answerable"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary-only", action="store_true", help="only check what an isolated run can see")
    args = parser.parse_args()

    canary = run_canary()
    leaks = leaked_terms(canary["output"]["mentions"])
    print("canary leaked terms:", leaks)
    if leaks:
        raise SystemExit(f"not blind, the run can see: {leaks}")
    if args.canary_only:
        return

    runs = {wording: [ask_persona(persona) for persona in personas] for wording, personas in PERSONAS.items()}
    batches = {wording: [run["output"]["questions"] for run in group] for wording, group in runs.items()}
    earlier = earlier_answerable()
    report = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "canary": {"project_terms_visible": leaks, "models": canary["models"]},
        "personas": PERSONAS,
        "models": sorted({model for group in runs.values() for run in group for model in run["models"]}),
        "earlier_answerable_questions": len(earlier),
        "questions": select_questions(batches, earlier),
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{report['timestamp_utc']}_questions.json").write_text(json.dumps(report, indent=2))
    for question in report["questions"]:
        print(f"{question['wording']:5s} {question['position']:2d} {question['role']:14s} {question['question']}")


if __name__ == "__main__":
    main()

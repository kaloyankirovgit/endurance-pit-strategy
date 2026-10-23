#!/usr/bin/env python3
"""Run the statistical-reviewer agent headless over the eval cases and score it.

Each call runs `claude -p` from an empty folder, so no project CLAUDE.md or memory leaks in,
with no tools and a fixed JSON schema for the answer.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from endurance_strategy.evals.reviewer import (
    REVIEW_INSTRUCTIONS,
    REVIEW_SCHEMA,
    agent_prompt,
    case_text,
    grade_run,
    summarise,
)

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / ".claude" / "agents" / "statistical-reviewer.md"
EVAL_DIR = ROOT / "evals" / "statistical_reviewer"


def review(case_file: Path, system_prompt: str, workdir: str) -> dict:
    result = subprocess.run(
        [
            "claude", "-p", REVIEW_INSTRUCTIONS + case_text(case_file),
            "--system-prompt", system_prompt,
            "--tools", "",
            "--json-schema", json.dumps(REVIEW_SCHEMA),
            "--output-format", "json",
            "--no-session-persistence",
        ],
        cwd=workdir, capture_output=True, text=True, timeout=600,
    )
    payload = json.loads(result.stdout)
    if payload.get("is_error") or "structured_output" not in payload:
        raise RuntimeError(f"{case_file.name}: {payload.get('result')}")
    return {"review": payload["structured_output"], "models": sorted(payload.get("modelUsage", {}))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cases", nargs="*", help="case ids to run (default: all)")
    args = parser.parse_args()

    labels = {row["id"]: row for row in json.loads((EVAL_DIR / "labels.json").read_text())}
    ids = args.cases or list(labels)
    system_prompt = agent_prompt(AGENT)
    jobs = [(case_id, repeat) for case_id in ids for repeat in range(args.repeats)]

    with tempfile.TemporaryDirectory() as workdir, ThreadPoolExecutor(args.workers) as pool:
        outputs = list(pool.map(lambda job: review(EVAL_DIR / "cases" / f"{job[0]}.md", system_prompt, workdir), jobs))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = []
    for (case_id, repeat), output in zip(jobs, outputs):
        label = labels[case_id]
        graded = grade_run(output["review"], label["planted"], label["accept"])
        runs.append({"case": case_id, "repeat": repeat, "planted": label["planted"], "models": output["models"], **graded,
                     "review": output["review"]})

    results_dir = EVAL_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    (results_dir / f"{stamp}_runs.jsonl").write_text("".join(json.dumps(run) + "\n" for run in runs))
    summary = {"timestamp_utc": stamp, "repeats": args.repeats, "cases": len(ids),
               "models": sorted({m for run in runs for m in run["models"]}), **summarise(runs)}
    (results_dir / f"{stamp}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

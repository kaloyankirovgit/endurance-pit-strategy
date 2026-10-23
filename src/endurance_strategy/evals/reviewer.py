from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

CATEGORIES = [
    "dependence",
    "sample_size",
    "leakage",
    "confounding",
    "identifiability",
    "model_assumptions",
    "uncertainty",
    "validation_design",
    "specification_sensitivity",
    "category_integrity",
    "null_alternative",
]
SEVERITIES = ["critical", "major", "minor"]
VERDICTS = ["supported", "supported with stated limitations", "not supported", "not identifiable"]
SERIOUS = {"critical", "major"}
DAMNING_VERDICTS = {"not supported", "not identifiable"}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_restated": {"type": "string"},
        "weaknesses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES},
                    "severity": {"type": "string", "enum": SEVERITIES},
                    "mechanism": {"type": "string"},
                },
                "required": ["category", "severity", "mechanism"],
            },
        },
        "verdict": {"type": "string", "enum": VERDICTS},
    },
    "required": ["claim_restated", "weaknesses", "verdict"],
}

REVIEW_INSTRUCTIONS = """Review the write-up below.

File each weakness under exactly one category: the attack from your instructions that it falls under. Severity means:
- critical: the conclusion does not stand as stated;
- major: the conclusion stands only after it is changed or qualified;
- minor: worth fixing, but the conclusion stands.

If you find no weakness worth reporting, return an empty list.

---

"""


def agent_prompt(agent_file: Path) -> str:
    """The agent's instructions without its YAML header."""
    text = agent_file.read_text()
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL).strip()


def case_text(case_file: Path) -> str:
    """The write-up the reviewer sees, with the synthetic-data header comment removed."""
    return re.sub(r"<!--.*?-->", "", case_file.read_text(), flags=re.DOTALL).strip()


def grade_run(review: dict, planted: str | None, accept: list[str]) -> dict:
    weaknesses = review.get("weaknesses", [])
    verdict = review.get("verdict")
    if planted is None:
        return {
            "kind": "control",
            "false_alarm": verdict in DAMNING_VERDICTS or any(w["severity"] == "critical" for w in weaknesses),
            "verdict": verdict,
        }
    hits = [w for w in weaknesses if w["category"] in accept]
    return {
        "kind": "flawed",
        "caught": bool(hits),
        "caught_serious": any(w["severity"] in SERIOUS for w in hits),
        "verdict_not_supported_as_is": verdict != "supported",
        "verdict": verdict,
    }


def summarise(graded: list[dict]) -> dict:
    """Rates over runs and over cases (a case counts if most of its repeats agree)."""
    flawed = [g for g in graded if g["kind"] == "flawed"]
    controls = [g for g in graded if g["kind"] == "control"]

    def majority(rows: list[dict], key: str) -> tuple[int, int]:
        by_case: dict[str, list[bool]] = {}
        for row in rows:
            by_case.setdefault(row["case"], []).append(row[key])
        return sum(sum(v) * 2 > len(v) for v in by_case.values()), len(by_case)

    def unstable(rows: list[dict], key: str) -> list[str]:
        by_case: dict[str, set] = {}
        for row in rows:
            by_case.setdefault(row["case"], set()).add(row[key])
        return sorted(case for case, values in by_case.items() if len(values) > 1)

    return {
        "flawed_runs": len(flawed),
        "caught_runs": sum(g["caught"] for g in flawed),
        "caught_serious_runs": sum(g["caught_serious"] for g in flawed),
        "flawed_cases_caught_serious_majority": majority(flawed, "caught_serious"),
        "control_runs": len(controls),
        "false_alarm_runs": sum(g["false_alarm"] for g in controls),
        "control_cases_false_alarm_majority": majority(controls, "false_alarm"),
        "unstable_cases": unstable(flawed, "caught_serious") + unstable(controls, "false_alarm"),
        "control_verdicts": dict(Counter(g["verdict"] for g in controls)),
    }

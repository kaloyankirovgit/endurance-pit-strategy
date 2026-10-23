from __future__ import annotations

import json
from pathlib import Path

from endurance_strategy.evals.reviewer import CATEGORIES, agent_prompt, case_text, grade_run, summarise

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evals" / "statistical_reviewer"


def weakness(category: str, severity: str) -> dict:
    return {"category": category, "severity": severity, "mechanism": "synthetic"}


def test_labels_cover_every_case_and_use_known_categories():
    labels = json.loads((EVAL_DIR / "labels.json").read_text())
    assert {row["id"] for row in labels} == {path.stem for path in (EVAL_DIR / "cases").glob("*.md")}
    for row in labels:
        if row["planted"] is None:
            assert row["accept"] == []
        else:
            assert row["planted"] in row["accept"]
            assert set(row["accept"]) <= set(CATEGORIES)


def test_every_case_is_marked_synthetic_and_the_marker_is_stripped():
    for path in (EVAL_DIR / "cases").glob("*.md"):
        assert path.read_text().startswith("<!-- SYNTHETIC")
        assert "SYNTHETIC" not in case_text(path)


def test_agent_prompt_drops_the_yaml_header():
    prompt = agent_prompt(ROOT / ".claude" / "agents" / "statistical-reviewer.md")
    assert not prompt.startswith("---")
    assert "tools:" not in prompt


def test_flawed_case_needs_an_accepted_category_at_major_or_above():
    accept = ["dependence", "uncertainty"]
    minor_only = grade_run({"weaknesses": [weakness("dependence", "minor")], "verdict": "supported"}, "dependence", accept)
    wrong_category = grade_run({"weaknesses": [weakness("leakage", "critical")], "verdict": "not supported"}, "dependence", accept)
    caught = grade_run({"weaknesses": [weakness("uncertainty", "major")], "verdict": "not supported"}, "dependence", accept)
    assert (minor_only["caught"], minor_only["caught_serious"]) == (True, False)
    assert (wrong_category["caught"], wrong_category["caught_serious"]) == (False, False)
    assert caught["caught_serious"] and caught["verdict_not_supported_as_is"]


def test_control_false_alarm_on_critical_weakness_or_damning_verdict():
    fine = grade_run({"weaknesses": [weakness("confounding", "major")], "verdict": "supported with stated limitations"}, None, [])
    critical = grade_run({"weaknesses": [weakness("confounding", "critical")], "verdict": "supported with stated limitations"}, None, [])
    damning = grade_run({"weaknesses": [], "verdict": "not supported"}, None, [])
    assert not fine["false_alarm"]
    assert critical["false_alarm"] and damning["false_alarm"]


def test_summary_counts_majorities_and_flags_unstable_cases():
    runs = [
        {"case": "a", "kind": "flawed", "caught": True, "caught_serious": True, "verdict": "not supported"},
        {"case": "a", "kind": "flawed", "caught": True, "caught_serious": True, "verdict": "not supported"},
        {"case": "a", "kind": "flawed", "caught": True, "caught_serious": False, "verdict": "supported"},
        {"case": "c", "kind": "control", "false_alarm": False, "verdict": "supported"},
    ]
    summary = summarise(runs)
    assert summary["caught_serious_runs"] == 2
    assert summary["flawed_cases_caught_serious_majority"] == (1, 1)
    assert summary["false_alarm_runs"] == 0
    assert summary["unstable_cases"] == ["a"]

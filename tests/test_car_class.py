from __future__ import annotations

import json
from pathlib import Path

import pytest

from endurance_strategy.rag import answer as answer_module
from endurance_strategy.rag.answer import CAR_CLASSES, UNCOVERED_CLASS_REFUSAL, answer_question
from endurance_strategy.rag.evaluate import contains_fact, grade_answer
from endurance_strategy.rag.retrieve import BM25

ROOT = Path(__file__).resolve().parents[1]

# Synthetic extracts, not taken from any real document.
CHUNKS = [
    {"chunk_id": "WEC-SR-2099:1.1", "season": "2099", "article": "1.1", "title": "2099 Synthetic Regulations",
     "revision": "v1", "page_start": 1, "text": "1.1 Tyres Free practice tyres: Hypercar 12, LMGT3 16."},
]


class FakeClaude:
    """Stands in for claude_json: records every prompt and returns canned outputs in call order."""

    def __init__(self, outputs: list[dict]):
        self.outputs, self.prompts = list(outputs), []

    def __call__(self, prompt, system_prompt, schema, workdir):
        self.prompts.append(prompt)
        return {"output": self.outputs.pop(0), "models": ["fake"]}


ROUTE = {"route": "regulation_lookup"}
SUPPORTED = {"supported": True, "answer": "You can use 16 tyres.", "refusal_reason": "",
             "citations": [{"chunk_id": "WEC-SR-2099:1.1", "quote": "LMGT3 16"}]}


def run(monkeypatch, car_class, outputs):
    fake = FakeClaude(outputs)
    monkeypatch.setattr(answer_module, "claude_json", fake)
    return answer_question("How many tyres in free practice?", "2099", BM25(CHUNKS), "/tmp", car_class=car_class), fake


def test_uncovered_class_is_refused_in_code_without_retrieval_or_an_answer_call(monkeypatch):
    trace, fake = run(monkeypatch, "LMP2", [ROUTE])
    assert len(fake.prompts) == 1
    assert trace["refused_in_code"] and trace["final"] == UNCOVERED_CLASS_REFUSAL
    assert "retrieved" not in trace


def test_unknown_class_raises_before_any_model_call(monkeypatch):
    fake = FakeClaude([])
    monkeypatch.setattr(answer_module, "claude_json", fake)
    with pytest.raises(ValueError):
        answer_question("q", "2099", BM25(CHUNKS), "/tmp", car_class="LMP3")
    assert fake.prompts == []


def test_chosen_class_reaches_the_answer_prompt(monkeypatch):
    trace, fake = run(monkeypatch, "LMGT3", [ROUTE, SUPPORTED])
    assert "(2099 season, LMGT3 class)" in fake.prompts[1]
    assert trace["final"] == "You can use 16 tyres."


def test_no_class_keeps_the_old_prompt(monkeypatch):
    _, fake = run(monkeypatch, None, [ROUTE, SUPPORTED])
    assert "(2099 season)" in fake.prompts[1]


def test_strategy_question_is_routed_away_before_the_class_check(monkeypatch):
    trace, fake = run(monkeypatch, "LMP2", [{"route": "simulation_request"}])
    assert trace["route"] == "simulation_request" and "refused_in_code" not in trace


def grade(final: str, wrong_facts: list[str]) -> dict:
    trace = {"route": "regulation_lookup", "check_problems": [], "retrieved": ["WEC-SR-2099:1.1"], "final": final,
             "answer": {**SUPPORTED, "answer": final}}
    question = {"id": "x", "season": "2099", "answerable": True, "gold_articles": ["1.1"],
                "key_facts": [["16"]], "wrong_facts": wrong_facts}
    return grade_answer(trace, question)


def test_other_class_figure_in_the_answer_is_caught():
    assert grade("LMGT3 gets 16 tyres and Hypercar 12.", ["12"])["wrong_facts_present"]


def test_wrong_fact_matches_whole_tokens_only():
    assert not grade("16 tyres, or 1812 km for the race.", ["18"])["wrong_facts_present"]


def test_refused_in_code_grades_as_nothing_shown():
    trace = {"route": "regulation_lookup", "refused_in_code": True, "check_problems": [], "final": UNCOVERED_CLASS_REFUSAL}
    graded = grade_answer(trace, {"id": "x", "answerable": False})
    assert graded["outcome"] == "refused_in_code" and graded["nothing_shown"]


def test_class_question_set_is_well_formed_and_paired():
    questions = json.loads((ROOT / "evals" / "regulations" / "questions_class.json").read_text())
    assert len({q["id"] for q in questions}) == len(questions)
    for q in questions:
        assert q["car_class"] in CAR_CLASSES
        assert bool(q["gold_articles"]) == q["answerable"] == (q["car_class"] != "LMP2")
    answerable = [q for q in questions if q["answerable"]]
    by_text = {}
    for q in answerable:
        by_text.setdefault(q["question"], set()).add(q["car_class"])
    assert all(classes == {"Hypercar", "LMGT3"} for classes in by_text.values())


def test_refused_run_is_not_counted_as_showing_a_wrong_fact():
    trace = {"route": "regulation_lookup", "check_problems": [], "retrieved": [], "final": "Not covered.",
             "answer": {**SUPPORTED, "supported": False, "answer": ""}}
    question = {"id": "x", "season": "2099", "answerable": True, "gold_articles": ["1.1"], "key_facts": [["16"]], "wrong_facts": ["12"]}
    graded = grade_answer(trace, question)
    assert not graded["shown"] and not graded["wrong_facts_present"]


def test_fact_match_ignores_article_numbers_and_longer_numbers():
    assert not contains_fact("See article 6.5.12 and the 1812km footnote.", "12")
    assert not contains_fact("Or 1812 km.", "18")
    assert contains_fact("You get 18 tyres.", "18")
    assert contains_fact("At least 1 hour 45 minutes.", "1 hour 45")


def test_key_and_wrong_facts_never_overlap():
    questions = json.loads((ROOT / "evals" / "regulations" / "questions_class.json").read_text())
    for q in questions:
        keys = {option for group in q["key_facts"] for option in group}
        assert not keys & set(q["wrong_facts"]), q["id"]


def test_word_prefix_facts_still_match():
    assert contains_fact("Penalties will be imposed.", "penalt")
    assert contains_fact("At the 15 minutes signal.", "15 minute")

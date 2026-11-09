from endurance_strategy.rag.evaluate import e019_decision
from endurance_strategy.rag.racer_agent import PERSONAS, SYSTEM_PROMPT, leaked_terms, overlap, round_robin, select_questions


def test_round_robin_takes_one_from_each_persona_in_turn():
    assert round_robin([["a1", "a2"], ["b1", "b2", "b3"]]) == ["a1", "b1", "a2", "b2", "b3"]


def test_overlap_ignores_case_punctuation_and_stop_words():
    assert overlap("How long is the pit stop?", "pit stop LONG") == 1.0
    assert overlap("tyres allowed", "yellow flags") == 0.0


def test_question_close_to_an_earlier_set_is_marked_and_not_counted():
    earlier = ["How many tyres can we use in the race?"]
    rows = select_questions({"racer": [["How many tyres can we use during the race?", "What does a red flag mean?"]]},
                            earlier, per_group=1)
    assert [r["role"] for r in rows] == ["near_duplicate", "main"]


def test_question_close_to_an_earlier_kept_question_is_marked():
    rows = select_questions({"fan": [["What does a red flag mean?"], ["What does the red flag mean?"]]}, [])
    assert [r["role"] for r in rows] == ["main", "near_duplicate"]


def test_questions_past_the_group_limit_go_to_the_reserve_in_order():
    rows = select_questions({"racer": [["Who changes the tyres?", "Can drivers refuel?", "What ends a race?"]]},
                            [], per_group=2)
    assert [r["role"] for r in rows] == ["main", "main", "reserve"]


def test_prompt_gives_the_agent_nothing_from_the_project():
    text = (SYSTEM_PROMPT + " ".join(p for group in PERSONAS.values() for p in group)).lower()
    for word in ("bm25", "hybrid", "retriev", "article", "corpus", "chunk", "clause"):
        assert word not in text


def test_canary_check_fires_when_the_project_is_visible():
    assert leaked_terms("Repo: endurance-pit-strategy-planner") == ["endurance-pit"]
    assert leaked_terms("NONE") == []


def test_e019_decision_follows_the_registered_rule():
    assert e019_decision(3, 0).startswith("inconclusive")
    assert e019_decision(3, 1) == "adopt the hybrid as the default"
    assert e019_decision(2, 2) == "BM25 stays and this hybrid configuration is dropped"
    assert e019_decision(1, 5) == "BM25 stays and this hybrid configuration is dropped"

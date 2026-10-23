from __future__ import annotations

from endurance_strategy.rag.answer import check_answer, normalise

# Synthetic extracts, not taken from any real document.
META = {"title": "2099 Synthetic Regulations", "revision": "v1", "page_start": 3}
RETRIEVED = [
    {**META, "chunk_id": "SYN:1.1", "article": "1.1", "text": "1.1 Pit lane speed The speed is limited to 60 kilometres per hour in the pit lane."},
    {**META, "chunk_id": "SYN:1.2", "article": "1.2", "text": "1.2 Driving time Each Bronze driver must drive 1h45 in a 6h race."},
]


def answer(text: str, citations: list[tuple[str, str]], supported: bool = True) -> dict:
    return {"supported": supported, "answer": text, "refusal_reason": "",
            "citations": [{"chunk_id": c, "quote": q} for c, q in citations]}


def test_grounded_answer_passes():
    good = answer("The pit lane limit is 60 km/h.", [("SYN:1.1", "limited to 60 kilometres per hour")])
    assert check_answer(good, RETRIEVED) == []


def test_refusal_is_not_checked():
    assert check_answer(answer("", [], supported=False), RETRIEVED) == []


def test_citation_of_a_chunk_that_was_not_retrieved_fails():
    bad = answer("The limit is 60 km/h.", [("SYN:9.9", "limited to 60")])
    assert any("not retrieved" in p for p in check_answer(bad, RETRIEVED))


def test_made_up_quote_fails():
    bad = answer("The limit is 60 km/h.", [("SYN:1.1", "limited to 60 km/h at all times")])
    assert any("quote not found" in p for p in check_answer(bad, RETRIEVED))


def test_number_missing_from_cited_extracts_fails_even_if_another_extract_has_it():
    bad = answer("Bronze drivers need 1h45 and the limit is 80 km/h.", [("SYN:1.1", "limited to 60 kilometres per hour")])
    problems = check_answer(bad, RETRIEVED)
    assert "number 80 is not in any cited extract" in problems
    assert "number 45 is not in any cited extract" in problems


def test_number_check_matches_whole_numbers_not_digits():
    bad = answer("The limit is 6 km/h.", [("SYN:1.1", "limited to 60 kilometres per hour")])
    assert "number 6 is not in any cited extract" in check_answer(bad, RETRIEVED)


def test_supported_answer_without_citations_fails():
    assert "supported answer has no citations" in check_answer(answer("It is 60.", []), RETRIEVED)


def test_normalise_matches_curly_quotes_and_spacing():
    assert normalise("Driver’s   “time”") == normalise("driver's \"time\"")


def test_number_from_the_extract_header_counts():
    good = answer("In the 2099 rules the limit is 60 km/h.", [("SYN:1.1", "limited to 60 kilometres per hour")])
    assert check_answer(good, RETRIEVED) == []

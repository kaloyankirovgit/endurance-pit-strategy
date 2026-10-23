from __future__ import annotations

from endurance_strategy.rag.regulations import Line, chunk_lines, is_contents_page

META = {"document_id": "SYN", "season": "2099"}
EDGE, INDENT, CENTRE = 240.0, 262.0, 300.0


def lines(rows: list[tuple[int, float, str]]) -> list[Line]:
    return [Line(page, x, 500.0 - i, text) for i, (page, x, text) in enumerate(rows)]


# Synthetic regulation text, not taken from any real document.
DOC = lines([
    (1, CENTRE, "1. GENERAL PROVISIONS"),
    (1, EDGE, "1.1 Foreword"),
    (1, EDGE, "The rules apply to every car."),
    (1, EDGE, "1.2 Pit stops"),
    (1, EDGE, "1.2.1 Refuelling"),
    (1, EDGE, "Refuelling is allowed only in the working lane, as set out in"),
    (1, INDENT, "1.2.3 of the code, and with the engine stopped."),
    (2, EDGE, "Only two mechanics may refuel."),
    (2, EDGE, "1.2.2 Driver change"),
    (2, EDGE, "A driver change may happen at any stop."),
    (2, CENTRE, "3. NOT NEXT IN SEQUENCE"),
    (2, EDGE, "Still part of 1.2.2."),
    (2, CENTRE, "2. RACE"),
    (2, EDGE, "2.1 Start"),
    (2, EDGE, "The race starts behind the safety car."),
    (3, EDGE, "APPENDIX 1: PERSONNEL"),
    (3, EDGE, "Teams may bring ten people."),
    (3, EDGE, "1.1 Engineers"),
    (3, EDGE, "Four engineers at most."),
])


def by_article(chunks: list[dict]) -> dict[str, dict]:
    return {chunk["article"]: chunk for chunk in chunks}


def test_one_chunk_per_lowest_heading_and_empty_parents_dropped():
    assert list(by_article(chunk_lines(DOC, META))) == ["1.1", "1.2.1", "1.2.2", "2.1", "APPENDIX 1", "APPENDIX 1/1.1"]


def test_number_inside_a_sentence_does_not_open_a_chunk():
    refuelling = by_article(chunk_lines(DOC, META))["1.2.1"]
    assert "1.2.3 of the code" in refuelling["text"]
    assert (refuelling["page_start"], refuelling["page_end"]) == (1, 2)


def test_main_articles_must_follow_in_sequence():
    driver_change = by_article(chunk_lines(DOC, META))["1.2.2"]
    assert "3. NOT NEXT IN SEQUENCE" in driver_change["text"]
    assert "Still part of 1.2.2." in driver_change["text"]


def test_chunk_carries_its_heading_path_and_metadata():
    chunk = by_article(chunk_lines(DOC, META))["1.2.1"]
    assert chunk["path"] == "1. GENERAL PROVISIONS > 1.2 Pit stops > 1.2.1 Refuelling"
    assert chunk["text"].startswith(chunk["path"])
    assert chunk["chunk_id"] == "SYN:1.2.1"
    assert chunk["season"] == "2099"


def test_appendix_headings_are_scoped_to_the_appendix():
    chunk = by_article(chunk_lines(DOC, META))["APPENDIX 1/1.1"]
    assert chunk["path"] == "APPENDIX 1: PERSONNEL > 1.1 Engineers"


def test_contents_pages_are_skipped():
    contents = lines([(9, EDGE, f"{n}.1 Some heading {n + 10}") for n in range(1, 8)])
    assert is_contents_page(contents)
    assert by_article(chunk_lines(DOC + contents, META)).keys() == by_article(chunk_lines(DOC, META)).keys()

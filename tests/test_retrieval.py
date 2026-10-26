from __future__ import annotations

import json
from pathlib import Path

from endurance_strategy.rag.evaluate import compare_hits, evaluate, season_variants, sign_test
from endurance_strategy.rag.retrieve import BM25, tokenise

ROOT = Path(__file__).resolve().parents[1]


def chunk(season: str, article: str, heading: str, text: str) -> dict:
    return {
        "chunk_id": f"WEC-SR-{season}:{article}", "document_id": f"WEC-SR-{season}", "season": season,
        "article": article, "path": f"1. RULES > {article} {heading}", "text": f"{article} {heading} {text}",
    }


# Synthetic regulation snippets, not taken from any real document.
CHUNKS = [
    chunk("2098", "1.1", "Refuelling", "Refuelling happens only in the stopping area with the engine off."),
    chunk("2098", "1.2", "Pit lane speed", "The pit lane speed limit is sixty kilometres per hour."),
    chunk("2098", "1.3", "Driving time", "Each driver must drive at least forty five minutes. " + "General wording. " * 40),
    chunk("2099", "1.1", "Refuelling", "Refuelling happens only in the stopping area with the engine off."),
    chunk("2099", "1.2", "Pit lane speed", "The pit lane speed limit is eighty kilometres per hour."),
]


def test_tokenise_lowercases_and_drops_stopwords():
    assert tokenise("The Pit-Lane speed IS 60 km/h") == ["pit", "lane", "speed", "60", "km", "h"]


def test_rare_matching_term_ranks_its_chunk_first():
    top, _ = BM25(CHUNKS).search("refuelling engine", k=1, season="2098")[0]
    assert top["article"] == "1.1"


def test_season_filter_returns_only_that_season():
    results = BM25(CHUNKS).search("pit lane speed limit", k=5, season="2099")
    assert {c["season"] for c, _ in results} == {"2099"}


def test_identical_text_across_seasons_ties_and_breaks_on_chunk_id():
    results = BM25(CHUNKS).search("refuelling stopping area", k=2)
    assert results[0][1] == results[1][1]
    assert [c["chunk_id"] for c, _ in results] == ["WEC-SR-2098:1.1", "WEC-SR-2099:1.1"]


def test_long_chunk_is_penalised_against_a_short_one_with_the_same_match():
    short = chunk("2098", "9.1", "Short", "driver minimum")
    long = chunk("2098", "9.2", "Long", "driver minimum " + "filler words here " * 60)
    retriever = BM25([short, long])
    assert retriever.score("driver minimum", 0) > retriever.score("driver minimum", 1)


def test_season_variants_map_gold_by_heading():
    question = {"id": "q", "season": "2099", "question": "speed in the pit lane", "gold_articles": ["1.2"], "answerable": True}
    variants = season_variants([question], CHUNKS, ["2098", "2097"])
    assert [(v["id"], v["gold_articles"]) for v in variants] == [("q@2098", ["1.2"])]


def test_evaluate_counts_a_wrong_season_hit_as_a_miss_without_the_filter():
    question = {"id": "q", "season": "2099", "question": "refuelling stopping area engine", "gold_articles": ["1.1"], "answerable": True}
    retriever = BM25(CHUNKS)
    with_filter = evaluate(retriever, [question], ks=(1,))
    without = evaluate(retriever, [question], ks=(1,), filter_season=False)
    assert with_filter["recall@1"] == 1
    assert without["recall@1"] == 0
    assert without["top1_right_article_wrong_season"] == 1


def test_question_set_is_well_formed():
    questions = json.loads((ROOT / "evals" / "regulations" / "questions.json").read_text())
    assert len({q["id"] for q in questions}) == len(questions)
    for q in questions:
        assert bool(q["gold_articles"]) == q["answerable"]


def test_sign_test_matches_hand_computed_binomial_tails():
    assert sign_test(5, 0) == 2 / 32
    assert sign_test(5, 1) == 2 * 7 / 64
    assert sign_test(1, 5) == sign_test(5, 1)
    assert sign_test(0, 0) == 1.0
    assert sign_test(3, 3) == 1.0


def test_compare_hits_counts_only_questions_where_the_two_disagree():
    result = lambda ranks: {"per_question": [{"id": i, "rank": r} for i, r in enumerate(ranks)]}
    challenger = result([1, 4, None, 6, 2])
    baseline = result([None, None, 3, None, 1])
    out = compare_hits(challenger, baseline, k=5)
    assert (out["wins"], out["losses"], out["questions"]) == (2, 1, 5)

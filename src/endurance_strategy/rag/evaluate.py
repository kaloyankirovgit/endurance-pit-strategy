from __future__ import annotations

from statistics import median

from endurance_strategy.rag.retrieve import BM25


def heading_of(chunk: dict) -> str:
    return chunk["path"].split(" > ")[-1]


def season_variants(questions: list[dict], chunks: list[dict], seasons: list[str]) -> list[dict]:
    """The same answerable questions asked of other seasons, with gold articles mapped by identical heading.

    A variant is kept only when every gold article has a chunk with the same heading in that season.
    """
    by_season_heading = {(chunk["season"], heading_of(chunk)): chunk["article"] for chunk in chunks}
    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    variants = []
    for question in questions:
        if not question["answerable"]:
            continue
        source_doc = f"WEC-SR-{question['season']}"
        headings = [heading_of(by_id[f"{source_doc}:{article}"]) for article in question["gold_articles"]]
        for season in seasons:
            mapped = [by_season_heading.get((season, heading)) for heading in headings]
            if all(mapped):
                variants.append({**question, "id": f"{question['id']}@{season}", "season": season, "gold_articles": mapped})
    return variants


def gold_ids(question: dict) -> set[str]:
    return {f"WEC-SR-{question['season']}:{article}" for article in question["gold_articles"]}


def evaluate(retriever: BM25, questions: list[dict], ks: tuple[int, ...] = (1, 3, 5), filter_season: bool = True) -> dict:
    """recall@k over answerable questions; with the season filter off, a hit must also be the right season."""
    answerable = [q for q in questions if q["answerable"]]
    per_question = []
    for question in answerable:
        results = retriever.search(question["question"], k=max(ks), season=question["season"] if filter_season else None)
        ids = [chunk["chunk_id"] for chunk, _ in results]
        gold = gold_ids(question)
        top = results[0][0]
        per_question.append({
            "id": question["id"],
            "rank": next((i + 1 for i, chunk_id in enumerate(ids) if chunk_id in gold), None),
            "top": ids[0],
            "top_wrong_season_same_article": top["season"] != question["season"] and top["article"] in question["gold_articles"],
            "retrieved": ids,
        })
    n = len(per_question)
    return {
        "questions": n,
        "filter_season": filter_season,
        **{f"recall@{k}": sum(r["rank"] is not None and r["rank"] <= k for r in per_question) for k in ks},
        "top1_right_article_wrong_season": sum(r["top_wrong_season_same_article"] for r in per_question),
        "per_question": per_question,
    }


def top_scores(retriever: BM25, questions: list[dict]) -> dict:
    """Best BM25 score for answerable and unanswerable questions, to see whether a score cut-off could support refusal."""
    scores = {True: [], False: []}
    for question in questions:
        scores[question["answerable"]].append(retriever.search(question["question"], k=1, season=question["season"])[0][1])
    return {
        "answerable": {"n": len(scores[True]), "median": median(scores[True]), "min": min(scores[True])},
        "unanswerable": {"n": len(scores[False]), "median": median(scores[False]), "max": max(scores[False])} if scores[False] else None,
    }


def grade_answer(trace: dict, question: dict) -> dict:
    """Outcome of one routed, retrieved, answered and checked question, scored against its labels."""
    from endurance_strategy.rag.answer import normalise

    route = trace["route"]
    answer = trace.get("answer")
    shown = route == "regulation_lookup" and answer is not None and answer["supported"] and not trace["check_problems"]
    if route != "regulation_lookup":
        outcome = "routed_away"
    elif not answer["supported"]:
        outcome = "refused"
    elif trace["check_problems"]:
        outcome = "rejected_by_check"
    else:
        outcome = "answered"

    graded = {"id": question["id"], "answerable": question["answerable"], "outcome": outcome, "route": route}
    if question["answerable"]:
        gold = gold_ids(question)
        cited = {c["chunk_id"] for c in answer["citations"]} if answer else set()
        final = normalise(trace["final"])
        graded.update({
            "retrieval_hit": bool(gold & set(trace.get("retrieved", []))),
            "cites_gold": shown and bool(gold & cited),
            "key_facts_checked": bool(question.get("key_facts")),
            "key_facts_present": shown and all(any(normalise(option) in final for option in group) for group in question.get("key_facts", [])),
        })
    else:
        graded["nothing_shown"] = not shown
    return graded

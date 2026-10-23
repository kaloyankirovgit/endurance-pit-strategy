from __future__ import annotations

import re
import unicodedata

from endurance_strategy.llm import claude_json
from endurance_strategy.rag.retrieve import BM25

ROUTES = ["regulation_lookup", "simulation_request", "out_of_scope"]

ROUTER_SYSTEM = """You sort questions sent to an endurance-racing strategy assistant. Pick exactly one route:
- regulation_lookup: what the FIA WEC sporting regulations allow, require or forbid.
- simulation_request: asks when to pit, which strategy is faster, or any number that would need a race simulation.
- out_of_scope: anything else, including results, Balance of Performance figures and general chat.
Return only the route."""

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {"route": {"type": "string", "enum": ROUTES}},
    "required": ["route"],
}

ANSWER_SYSTEM = """You answer questions about the FIA WEC sporting regulations using only the regulation extracts you are given.

Rules:
- Use only the extracts. Never use outside knowledge, even if you are confident.
- If the extracts do not answer the question, set "supported" to false, leave "answer" empty and say in "refusal_reason" what is missing.
- If they do, answer in one to three plain sentences and cite every extract you relied on by its chunk_id, with a short quote copied word for word from that extract.
- Every number in your answer must appear in an extract you cite.
- Do not decide or recommend pit timing or strategy. That is the simulator's job."""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"chunk_id": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["chunk_id", "quote"],
            },
        },
        "refusal_reason": {"type": "string"},
    },
    "required": ["supported", "answer", "citations", "refusal_reason"],
}

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def normalise(text: str) -> str:
    """Lowercase, straight quotes, single spaces: so a quote copied from extracted PDF text can be matched."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    return " ".join(text.lower().split())


def format_extracts(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"[chunk_id: {c['chunk_id']}] {c['title']}, revision {c['revision']}, article {c['article']}, page {c['page_start']}\n{c['text']}"
        for c in chunks
    )


def check_answer(answer: dict, retrieved: list[dict]) -> list[str]:
    """Problems that mean the answer can't be trusted. An empty list means it passed.

    Deterministic: every citation is a retrieved chunk, every quote appears in that chunk,
    and every number in the answer appears in a cited extract as the model saw it (header included).
    """
    if not answer["supported"]:
        return []
    by_id = {c["chunk_id"]: c for c in retrieved}
    problems = []
    if not answer["answer"].strip():
        problems.append("supported answer is empty")
    if not answer["citations"]:
        problems.append("supported answer has no citations")
    cited_numbers: set[str] = set()
    for citation in answer["citations"]:
        chunk = by_id.get(citation["chunk_id"])
        if chunk is None:
            problems.append(f"cites {citation['chunk_id']}, which was not retrieved")
            continue
        cited_numbers |= set(NUMBER.findall(format_extracts([chunk])))
        if normalise(citation["quote"]) not in normalise(chunk["text"]):
            problems.append(f"quote not found in {citation['chunk_id']}")
    for number in NUMBER.findall(answer["answer"]):
        if number not in cited_numbers:
            problems.append(f"number {number} is not in any cited extract")
    return problems


def answer_question(question: str, season: str, retriever: BM25, workdir: str, k: int = 5) -> dict:
    """Route, retrieve, answer, check. Everything is returned so the trace can be logged."""
    route_call = claude_json(question, ROUTER_SYSTEM, ROUTER_SCHEMA, workdir)
    trace = {"question": question, "season": season, "route": route_call["output"]["route"], "models": route_call["models"]}
    if trace["route"] != "regulation_lookup":
        trace["final"] = {
            "simulation_request": "Strategy questions need the race simulator, which isn't built yet. The assistant won't answer them in prose.",
            "out_of_scope": "This assistant only answers questions about the WEC sporting regulations.",
        }[trace["route"]]
        return trace

    retrieved = [chunk for chunk, _ in retriever.search(question, k=k, season=season)]
    answer_call = claude_json(f"Question ({season} season): {question}\n\nExtracts:\n\n{format_extracts(retrieved)}",
                              ANSWER_SYSTEM, ANSWER_SCHEMA, workdir)
    answer = answer_call["output"]
    problems = check_answer(answer, retrieved)
    trace.update({
        "retrieved": [c["chunk_id"] for c in retrieved],
        "answer": answer,
        "check_problems": problems,
        "models": sorted(set(trace["models"]) | set(answer_call["models"])),
    })
    if not answer["supported"]:
        trace["final"] = f"The regulations provided don't answer this. {answer['refusal_reason']}"
    elif problems:
        trace["final"] = "An answer was drafted but failed the citation check, so it isn't shown."
    else:
        trace["final"] = answer["answer"]
    return trace

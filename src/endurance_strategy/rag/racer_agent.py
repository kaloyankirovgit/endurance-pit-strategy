"""The racer agent: a blind model that writes the questions a driver or fan would ask (E-019).

It runs headless from an empty folder with no tools, so it sees nothing of this project,
the regulations or the earlier question sets.
"""
from __future__ import annotations

import re
import tempfile
from itertools import zip_longest

from endurance_strategy.llm import claude_json

QUESTIONS_PER_PERSONA = 10
PER_GROUP = 25
NEAR_DUPLICATE_OVERLAP = 0.6
# Drop the user's settings and connected tools as well as the project's.
ISOLATION_ARGS = ("--setting-sources", "", "--strict-mcp-config")
PROJECT_TERMS = ("endurance-pit", "endurance_strategy", "bm25", "wec", "regulation")

PERSONAS = {
    "racer": (
        "You are an amateur driver sharing a GT3 car in a six-hour FIA WEC race, and you've just climbed in for your stint.",
        "You are a professional driver in a Hypercar, part way through an FIA WEC race.",
        "You are a sim racer in a long online endurance race, driving with friends in a game that copies the FIA WEC rules.",
        "You are a sim racer who only knows sprint races and has just joined an online league that runs the FIA WEC rules.",
    ),
    "fan": (
        "You are at your first FIA WEC race, sitting in the grandstand at the 6 Hours of Spa with a friend.",
        "You have followed the FIA WEC for years and are watching tonight's race on the live stream at home.",
        "You are a Formula 1 fan who has turned on an FIA WEC race for the first time.",
        "You are a relative of one of the drivers, watching an FIA WEC race from the hospitality area.",
    ),
}

SYSTEM_PROMPT = """Play the person described below and stay in character. The season is 2026.

{persona}

You have no rulebook, phone or anything else to look things up with. Write {count} different questions you would ask someone who knows the rules of this race: what competitors can and can't do, how things work during the race, and what happens when something goes wrong.

Use your own everyday words, the way you'd say it out loud. Keep each question to one or two sentences. Don't ask who will win, about how a particular driver or team is doing, or for advice on strategy."""

SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
    "required": ["questions"],
    "additionalProperties": False,
}

CANARY_SYSTEM_PROMPT = "Answer plainly and only from what is in this conversation and your instructions."
CANARY_PROMPT = (
    "Quote every software project, repository, file name, person's name or email address that appears "
    "in your instructions or context. If there are none, write NONE."
)
CANARY_SCHEMA = {
    "type": "object",
    "properties": {"mentions": {"type": "string"}},
    "required": ["mentions"],
    "additionalProperties": False,
}

STOP_WORDS = frozenset(
    "a an and are as at be but by can do does for from happens have how i if in is it its me my of on or our so "
    "that the their them they this to us was we what when where which who why will with would you your".split()
)


def run_canary() -> dict:
    """Ask a run with the same isolation what it can see, to check it really is blind."""
    with tempfile.TemporaryDirectory() as workdir:
        return claude_json(CANARY_PROMPT, CANARY_SYSTEM_PROMPT, CANARY_SCHEMA, workdir, extra_args=ISOLATION_ARGS)


def leaked_terms(canary_text: str) -> list[str]:
    """Project terms a blind run shouldn't be able to quote."""
    return [term for term in PROJECT_TERMS if term in canary_text.lower()]


def ask_persona(persona: str) -> dict:
    with tempfile.TemporaryDirectory() as workdir:
        system_prompt = SYSTEM_PROMPT.format(persona=persona, count=QUESTIONS_PER_PERSONA)
        return claude_json(f"Write your {QUESTIONS_PER_PERSONA} questions.", system_prompt, SCHEMA, workdir,
                           extra_args=ISOLATION_ARGS)


def content_words(question: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", question.lower())) - STOP_WORDS


def overlap(first: str, second: str) -> float:
    """Jaccard overlap of the content words in two questions."""
    a, b = content_words(first), content_words(second)
    return len(a & b) / len(a | b) if a | b else 0.0


def round_robin(batches: list[list[str]]) -> list[str]:
    """First question from each persona, then the second from each, and so on."""
    return [question for row in zip_longest(*batches) for question in row if question is not None]


def select_questions(batches_by_group: dict[str, list[list[str]]], earlier: list[str],
                     per_group: int = PER_GROUP) -> list[dict]:
    """Put every question in its fixed order, marking near-duplicates and the main set against the reserve."""
    seen = list(earlier)
    selected = []
    for wording, batches in batches_by_group.items():
        kept = 0
        for position, question in enumerate(round_robin(batches)):
            duplicate = any(overlap(question, other) >= NEAR_DUPLICATE_OVERLAP for other in seen)
            if duplicate:
                role = "near_duplicate"
            else:
                role = "main" if kept < per_group else "reserve"
                kept += 1
                seen.append(question)
            selected.append({"wording": wording, "position": position, "question": question, "role": role})
    return selected

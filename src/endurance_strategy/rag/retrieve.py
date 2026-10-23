from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = set("""
a an and are as at be by can do does for from has have how if in into is it its may must
of on or that the their them then there these this to under was what when where which who
will with within without would should car cars
""".split())
TOKEN = re.compile(r"[a-z0-9]+")


def tokenise(text: str) -> list[str]:
    return [token for token in TOKEN.findall(text.lower()) if token not in STOPWORDS]


class BM25:
    """Okapi BM25 over chunk texts.

    k1 sets how fast repeats of a word stop adding score; b sets how strongly long chunks are
    penalised. Defaults are the usual textbook values, not tuned on the question set.
    """

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.term_counts = [Counter(tokenise(chunk["text"])) for chunk in chunks]
        self.lengths = [sum(counts.values()) for counts in self.term_counts]
        self.mean_length = sum(self.lengths) / len(self.lengths)
        document_frequency = Counter(term for counts in self.term_counts for term in counts)
        n = len(chunks)
        self.idf = {term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in document_frequency.items()}

    def score(self, query: str, index: int) -> float:
        counts, length = self.term_counts[index], self.lengths[index]
        total = 0.0
        for term in tokenise(query):
            frequency = counts.get(term, 0)
            if frequency:
                saturation = frequency * (self.k1 + 1) / (frequency + self.k1 * (1 - self.b + self.b * length / self.mean_length))
                total += self.idf[term] * saturation
        return total

    def search(self, query: str, k: int = 5, season: str | None = None) -> list[tuple[dict, float]]:
        """Top-k chunks, optionally only from the regulations of one season."""
        candidates = [i for i, chunk in enumerate(self.chunks) if season is None or chunk["season"] == season]
        scored = sorted(((self.score(query, i), i) for i in candidates), key=lambda pair: (-pair[0], self.chunks[pair[1]]["chunk_id"]))
        return [(self.chunks[i], score) for score, i in scored[:k]]

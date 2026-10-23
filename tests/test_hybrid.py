from __future__ import annotations

from endurance_strategy.rag.embed import HybridRetriever


class Stub:
    def __init__(self, order: list[str]):
        self.order = order

    def search(self, query, k=5, season=None):
        return [({"chunk_id": chunk_id}, 1.0) for chunk_id in self.order[:k]]


def test_a_chunk_ranked_well_by_both_beats_one_ranked_first_by_only_one():
    hybrid = HybridRetriever(Stub(["a", "b", "c", "e"]), Stub(["d", "b", "f", "a"]))
    assert [c["chunk_id"] for c, _ in hybrid.search("q", k=4)] == ["b", "a", "d", "c"]


def test_fusion_score_is_sum_of_reciprocal_ranks():
    hybrid = HybridRetriever(Stub(["a"]), Stub(["a"]), constant=60)
    (_, score), = hybrid.search("q", k=1)
    assert score == 2 / 61

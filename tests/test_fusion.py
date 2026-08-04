import pytest

from rag_app.retrieval.fusion import reciprocal_rank_fusion


def test_reciprocal_rank_fusion_rewards_results_from_both_rankings() -> None:
    fused = reciprocal_rank_fusion(
        [["vector-only", "both", "tail"], ["both", "lexical-only"]], k=60
    )

    assert fused[0][0] == "both"
    assert {item_id for item_id, _score in fused} == {
        "vector-only",
        "both",
        "tail",
        "lexical-only",
    }


def test_reciprocal_rank_fusion_is_deterministic_on_ties() -> None:
    result = reciprocal_rank_fusion([["b", "a"], ["a", "b"]], k=1)
    assert [item_id for item_id, _score in result] == ["a", "b"]
    assert [score for _item_id, score in result] == pytest.approx([5 / 6, 5 / 6])

"""RRF fusion tests (A4.1) with deterministic golden values."""

from __future__ import annotations

import pytest

from tracefix.graph.models import Provenance
from tracefix.retrieval.fusion import DEFAULT_RRF_K, fuse, reciprocal_rank_fusion
from tracefix.retrieval.interfaces import (
    EvidenceTarget,
    RankedItem,
    RetrievalResult,
)

REV = "9" * 40


def test_rrf_golden_two_rankings() -> None:
    # k=60: a=1/61+1/61; b=1/62+1/63; c=1/63+1/62 -> b==c, tie-break by id
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["a", "c", "b"]], k=60)
    ids = [evidence_id for evidence_id, _ in fused]
    assert ids == ["a", "b", "c"]
    scores = dict(fused)
    assert scores["a"] == pytest.approx(2 / 61)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 63)
    assert scores["c"] == pytest.approx(1 / 63 + 1 / 62)


def test_rrf_single_ranking_is_inverse_rank_transform() -> None:
    fused = dict(reciprocal_rank_fusion([["x", "y"]], k=60))
    assert fused["x"] == pytest.approx(1 / 61)
    assert fused["y"] == pytest.approx(1 / 62)


def test_rrf_rejects_invalid_k() -> None:
    with pytest.raises(ValueError, match="k must be"):
        reciprocal_rank_fusion([["a"]], k=0)


def test_rrf_is_order_insensitive_for_scores() -> None:
    forward = dict(reciprocal_rank_fusion([["a", "b"], ["b", "a"]]))
    backward = dict(reciprocal_rank_fusion([["b", "a"], ["a", "b"]]))
    assert forward == backward


def _result(ids: list[str], strategy: str) -> RetrievalResult:
    items = [
        RankedItem(
            evidence_id=eid,
            strategy=strategy,
            rank=rank,
            score=10.0 - rank,
            target=EvidenceTarget(file=f"{eid}.py"),
            source_revision=REV,
            provenance=Provenance.OBSERVED,
            source="bm25",
        )
        for rank, eid in enumerate(ids, start=1)
    ]
    return RetrievalResult(
        items=items,
        complete=True,
        strategy=strategy,
        revision=REV,
        elapsed_ms=1.0,
    )


def test_fuse_dispatches_rrf_and_honors_top_n() -> None:
    results = [_result(["a", "b", "c"], "lexical"), _result(["c", "d"], "graph_guided")]
    fused = fuse(results, method="rrf", k=DEFAULT_RRF_K, top_n=2)
    assert len(fused) == 2
    assert fused[0][0] in {"a", "b", "c"}


def test_fuse_unknown_method_raises() -> None:
    with pytest.raises(ValueError, match="unknown fusion method"):
        fuse([_result(["a"], "lexical")], method="dbsf")


def test_fuse_empty_inputs() -> None:
    assert fuse([]) == []

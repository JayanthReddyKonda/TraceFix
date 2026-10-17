"""Score fusion (task A4.1/A4.3): Reciprocal Rank Fusion, method-selectable.

DBSF is intentionally absent (Checkpoint 0, D7): it may be added only together
with a cited authoritative definition, never as a renamed substitute.
"""

from __future__ import annotations

from collections.abc import Sequence

from tracefix.retrieval.interfaces import RetrievalResult

DEFAULT_RRF_K = 60
SUPPORTED_METHODS = ("rrf",)


def reciprocal_rank_fusion(
    ranked_id_lists: Sequence[Sequence[str]], k: int = DEFAULT_RRF_K
) -> list[tuple[str, float]]:
    """RRF: score(d) = sum over rankings of 1 / (k + rank_i(d)).

    rank_i is 1-based. Ties break by ascending evidence id so output order is
    deterministic. Input order of the rankings does not affect scores, only
    which list contributes which ranks.
    """
    if k < 1:
        raise ValueError(f"rrf k must be >= 1, got {k}")
    scores: dict[str, float] = {}
    for ranking in ranked_id_lists:
        for rank, evidence_id in enumerate(ranking, start=1):
            scores[evidence_id] = scores.get(evidence_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


def fuse_ids(
    ranked_id_lists: Sequence[Sequence[str]],
    method: str = "rrf",
    k: int = DEFAULT_RRF_K,
    top_n: int | None = None,
) -> list[tuple[str, float]]:
    """Fuse pre-ranked evidence-id lists into (evidence_id, score) pairs.

    Lower-level entry point for callers that have already filtered items (for
    example, the pipeline drops revision-mismatched items before fusing).
    """
    if method not in SUPPORTED_METHODS:
        raise ValueError(
            f"unknown fusion method {method!r}; supported: {sorted(SUPPORTED_METHODS)}"
        )
    if not ranked_id_lists:
        return []
    fused = reciprocal_rank_fusion(ranked_id_lists, k=k)
    return fused if top_n is None else fused[:top_n]


def fuse(
    result_sets: Sequence[RetrievalResult],
    method: str = "rrf",
    k: int = DEFAULT_RRF_K,
    top_n: int | None = None,
) -> list[tuple[str, float]]:
    """Fuse complete or partial result sets into (evidence_id, score) pairs."""
    rankings = [[item.evidence_id for item in result.items] for result in result_sets]
    return fuse_ids(rankings, method=method, k=k, top_n=top_n)

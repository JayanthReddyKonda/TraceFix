"""Retrieval pipeline tests (A3.6): fusion, dedup, revision, failures, context."""

from __future__ import annotations

from pathlib import Path

import pytest

from tracefix.graph.ingestion import ingest_repository
from tracefix.graph.models import Provenance
from tracefix.graph.query import GraphUnavailableError, SnapshotNeighborhoodProvider
from tracefix.retrieval.context_selector import CharDiv4TokenCounter, ContextSelector
from tracefix.retrieval.graph_guided import GraphGuidedStrategy
from tracefix.retrieval.interfaces import (
    EvidenceTarget,
    PartialReason,
    RankedItem,
    RetrievalError,
    RetrievalLimits,
    RetrievalQuery,
    RetrievalResult,
)
from tracefix.retrieval.lexical import LexicalBM25Strategy, build_function_corpus
from tracefix.retrieval.pipeline import RetrievalPipeline

REV = "a" * 40


def item(
    eid: str,
    rank: int,
    *,
    file: str = "m.py",
    source: str = "bm25",
    strategy: str = "lexical",
    provenance: Provenance = Provenance.OBSERVED,
    revision: str = REV,
) -> RankedItem:
    return RankedItem(
        evidence_id=eid,
        strategy=strategy,
        rank=rank,
        score=1.0 / rank,
        target=EvidenceTarget(file=file, symbol=eid, lines=(1, 2)),
        source_revision=revision,
        provenance=provenance,
        source=source,
    )


class StaticStrategy:
    def __init__(self, name: str, items: list[RankedItem]) -> None:
        self.name = name
        self._items = items

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        return RetrievalResult(
            items=self._items,
            complete=True,
            strategy=self.name,
            revision=query.revision,
            elapsed_ms=0.0,
        )


class EmptyStrategy(StaticStrategy):
    def __init__(self, name: str = "empty") -> None:
        super().__init__(name, [])


class IncompleteStrategy(StaticStrategy):
    def __init__(self, name: str, reason: PartialReason, items: list[RankedItem]) -> None:
        super().__init__(name, items)
        self._reason = reason

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        return RetrievalResult(
            items=self._items,
            complete=False,
            partial_reason=self._reason,
            strategy=self.name,
            revision=query.revision,
            elapsed_ms=0.0,
        )


class FailingStrategy:
    name = "failing"

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        raise RuntimeError("arm exploded")


class ExplainingProvider:
    """Provider that always reports the graph as unavailable."""

    def neighborhood(self, seed_ids, **kwargs):  # type: ignore[no-untyped-def]
        raise GraphUnavailableError("no graph")


def _query(text: str = "anything", *, max_items: int = 10, max_hops: int = 0) -> RetrievalQuery:
    return RetrievalQuery(
        case_id="c",
        text=text,
        revision=REV,
        k=max_items,
        limits=RetrievalLimits(max_items=max_items, max_hops=max_hops, timeout_ms=5000),
    )


def test_single_strategy_fused_ranks_dense() -> None:
    pipeline = RetrievalPipeline([StaticStrategy("a", [item("e1", 1), item("e2", 2)])])
    result = pipeline.retrieve(_query())
    assert result.strategy == "fusion"
    assert [i.evidence_id for i in result.items] == ["e1", "e2"]
    assert [i.rank for i in result.items] == [1, 2]
    assert result.complete is True


def test_duplicates_across_arms_deduplicated() -> None:
    arm_a = StaticStrategy("a", [item("e1", 1), item("e2", 2)])
    arm_b = StaticStrategy("b", [item("e2", 1), item("e3", 2)])
    result = RetrievalPipeline([arm_a, arm_b]).retrieve(_query())
    ids = [i.evidence_id for i in result.items]
    # e2 appears in both arms, so RRF ranks it first; ids stay unique.
    assert ids == ["e2", "e1", "e3"]
    assert len(ids) == len(set(ids))
    assert result.config["duplicates_removed"] == 1


def test_ordering_is_strategy_order_insensitive() -> None:
    arm_a = StaticStrategy("a", [item("e1", 1), item("e2", 2)])
    arm_b = StaticStrategy("b", [item("e3", 1), item("e4", 2)])
    forward = RetrievalPipeline([arm_a, arm_b]).retrieve(_query())
    backward = RetrievalPipeline([arm_b, arm_a]).retrieve(_query())
    assert [i.evidence_id for i in forward.items] == [i.evidence_id for i in backward.items]


def test_provenance_of_first_arm_wins() -> None:
    arm_a = StaticStrategy(
        "a", [item("e1", 1, provenance=Provenance.INFERRED, source="graph_callees")]
    )
    arm_b = StaticStrategy("b", [item("e1", 1, provenance=Provenance.OBSERVED, source="bm25")])
    result = RetrievalPipeline([arm_a, arm_b]).retrieve(_query())
    assert result.items[0].provenance is Provenance.INFERRED
    assert result.items[0].source == "graph_callees"


def test_empty_result_is_complete() -> None:
    result = RetrievalPipeline([EmptyStrategy()]).retrieve(_query())
    assert result.items == []
    assert result.complete is True
    assert result.partial_reason is None


def test_incomplete_arm_degrades_pipeline() -> None:
    arm = IncompleteStrategy("g", PartialReason.GRAPH_UNAVAILABLE, [item("e1", 1)])
    result = RetrievalPipeline([arm]).retrieve(_query())
    assert result.complete is False
    assert result.partial_reason is PartialReason.GRAPH_UNAVAILABLE
    assert [i.evidence_id for i in result.items] == ["e1"]


def test_partial_reason_precedence() -> None:
    arm_a = IncompleteStrategy("a", PartialReason.LIMIT_REACHED, [item("e1", 1)])
    arm_b = IncompleteStrategy("b", PartialReason.TIMEOUT, [item("e2", 1)])
    result = RetrievalPipeline([arm_a, arm_b]).retrieve(_query())
    assert result.partial_reason is PartialReason.TIMEOUT


def test_strategy_failure_is_isolated() -> None:
    pipeline = RetrievalPipeline([FailingStrategy(), StaticStrategy("ok", [item("e1", 1)])])
    result = pipeline.retrieve(_query())
    assert [i.evidence_id for i in result.items] == ["e1"]
    assert result.complete is False
    assert result.partial_reason is PartialReason.STRATEGY_ERROR_RECOVERED
    statuses = {o["strategy"]: o["status"] for o in result.config["outcomes"]}
    assert statuses == {"failing": "error", "ok": "ok"}


def test_all_strategies_failing_raises() -> None:
    with pytest.raises(RetrievalError):
        RetrievalPipeline([FailingStrategy()]).retrieve(_query())


def test_revision_mismatch_items_dropped_and_flagged() -> None:
    arm = StaticStrategy("a", [item("e1", 1, revision="b" * 40)])
    result = RetrievalPipeline([arm]).retrieve(_query())
    assert result.items == []
    assert result.config["revision_mismatches"] == 1
    assert result.partial_reason is PartialReason.STRATEGY_ERROR_RECOVERED


def test_max_items_truncation_reports_limit_reached() -> None:
    arm = StaticStrategy("a", [item("e1", 1), item("e2", 2), item("e3", 3)])
    result = RetrievalPipeline([arm]).retrieve(_query(max_items=2))
    assert len(result.items) == 2
    assert result.partial_reason is PartialReason.LIMIT_REACHED


def test_missing_strategies_rejected() -> None:
    with pytest.raises(ValueError):
        RetrievalPipeline([])


def test_unknown_fusion_method_rejected() -> None:
    with pytest.raises(ValueError):
        RetrievalPipeline([EmptyStrategy()], method="dbsf")


def test_fused_result_satisfies_c2_semantics() -> None:
    arm_a = StaticStrategy("a", [item("e1", 1), item("e2", 2)])
    arm_b = IncompleteStrategy("b", PartialReason.LIMIT_REACHED, [item("e2", 1), item("e3", 2)])
    result = RetrievalPipeline([arm_a, arm_b]).retrieve(_query())
    assert [i.rank for i in result.items] == list(range(1, len(result.items) + 1))
    if not result.complete:
        assert result.partial_reason is not None
    assert all(i.provenance is not None and i.source for i in result.items)


def _lexical(ingested, repo: Path) -> LexicalBM25Strategy:
    return LexicalBM25Strategy(build_function_corpus(repo, ingested.nodes))


def _graph(ingested, repo: Path, seed_count: int = 3) -> GraphGuidedStrategy:
    provider = SnapshotNeighborhoodProvider(ingested.nodes, ingested.edges, direction="out")
    return GraphGuidedStrategy(provider, _lexical(ingested, repo), seed_count=seed_count)


def test_end_to_end_lexical_plus_graph(mini_repo: Path, mini_repo_url: str) -> None:
    ingested = ingest_repository(mini_repo, mini_repo_url, ingested_at="2026-10-16T00:00:00+00:00")
    pipeline = RetrievalPipeline([_lexical(ingested, mini_repo), _graph(ingested, mini_repo)])
    query = RetrievalQuery(
        case_id="c",
        text="accumulate values loop total",
        revision=ingested.revision,
        k=10,
        limits=RetrievalLimits(max_items=10, max_hops=1, timeout_ms=5000),
    )
    result = pipeline.retrieve(query)
    assert result.items
    assert all(i.source_revision == ingested.revision for i in result.items)
    ids = [i.evidence_id for i in result.items]
    assert len(ids) == len(set(ids))
    assert [i.rank for i in result.items] == list(range(1, len(result.items) + 1))
    assert result.config["strategies"] == ["lexical", "graph_guided"]
    # determinism
    rebuilt = RetrievalPipeline([_lexical(ingested, mini_repo), _graph(ingested, mini_repo)])
    again = rebuilt.retrieve(query)
    assert [i.evidence_id for i in again.items] == ids


def test_graph_unavailable_arm_degrades_end_to_end(mini_repo: Path, mini_repo_url: str) -> None:
    ingested = ingest_repository(mini_repo, mini_repo_url, ingested_at="2026-10-16T00:00:00+00:00")
    lexical = _lexical(ingested, mini_repo)
    broken_graph = GraphGuidedStrategy(ExplainingProvider(), lexical, seed_count=3)  # type: ignore[arg-type]
    query = RetrievalQuery(
        case_id="c",
        text="accumulate values loop total",
        revision=ingested.revision,
        k=10,
        limits=RetrievalLimits(max_items=10, max_hops=1, timeout_ms=5000),
    )
    result = RetrievalPipeline([lexical, broken_graph]).retrieve(query)
    assert result.complete is False
    assert result.partial_reason is PartialReason.GRAPH_UNAVAILABLE
    assert result.items  # lexical seeds still returned via the graph arm's seeds


def test_explain_and_context_integration(mini_repo: Path, mini_repo_url: str) -> None:
    ingested = ingest_repository(mini_repo, mini_repo_url, ingested_at="2026-10-16T00:00:00+00:00")
    pipeline = RetrievalPipeline([_lexical(ingested, mini_repo), _graph(ingested, mini_repo)])
    query = RetrievalQuery(
        case_id="c",
        text="accumulate values loop total",
        revision=ingested.revision,
        k=10,
        limits=RetrievalLimits(max_items=10, max_hops=1, timeout_ms=5000),
    )
    result = pipeline.retrieve(query)
    expanded = [i for i in result.items if pipeline.explain(i.evidence_id) is not None]
    assert expanded, "expected at least one expanded item with a graph path"

    candidates = pipeline.to_candidates(result, lambda i: f"{i.target.file}::{i.target.symbol}")
    assert any(c.graph_path is not None for c in candidates)
    selection = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=1000)
    assert selection.totals.tokens <= selection.budget.token_limit
    assert selection.totals.item_count == len(selection.items)

"""Graph-guided retrieval tests (A3.3): expansion, dedup, provenance, failure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tracefix.graph.ingestion import ingest_repository
from tracefix.graph.models import Edge, Node, Provenance
from tracefix.graph.query import (
    GraphPath,
    GraphUnavailableError,
    Neighborhood,
    SnapshotNeighborhoodProvider,
)
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

REV = "a" * 40
REPO = "https://example.test/repo"


def nid(kind: str, key: str) -> str:
    return f"{REPO}#{kind}:{key}"


def _node(kind: str, key: str, **props: Any) -> Node:
    return Node(
        entity_id=nid(kind, key),
        kind=kind,
        repo=REPO,
        revision=REV,
        properties=dict(props),
        ingested_at="2026-10-16T00:00:00+00:00",
    )


def _edge(
    edge_type: str,
    source_id: str,
    target_id: str,
    *,
    provenance: Provenance = Provenance.OBSERVED,
    source: str = "name-resolution",
    confidence: str | None = None,
) -> Edge:
    return Edge(
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        provenance=provenance,
        source=source,
        revision=REV,
        confidence=confidence,
    )


def _sym(
    key: str, path: str, start: int, end: int, *, kind: str = "Function", suffix: str = "m"
) -> Node:
    return _node(
        kind, key, path=path, qualified_name=f"{suffix}.{key}", start_line=start, end_line=end
    )


def _snapshot() -> tuple[dict[str, Node], list[Edge]]:
    nodes = {
        nid("Function", "a"): _sym("a", "m.py", 1, 2),
        nid("Function", "b"): _sym("b", "m.py", 4, 5),
        nid("Function", "c"): _sym("c", "m.py", 7, 8),
        nid("Function", "d"): _sym("d", "n.py", 1, 2, suffix="n"),
        nid("Test", "t"): _sym("t", "tests/test_m.py", 1, 2, kind="Test", suffix="tests.test_m"),
    }
    edges = [
        _edge("CALLS", nid("Function", "a"), nid("Function", "b")),
        _edge("CALLS", nid("Function", "b"), nid("Function", "d")),
        _edge(
            "CALLS",
            nid("Function", "a"),
            nid("Function", "c"),
            provenance=Provenance.INFERRED,
            source="name-heuristic",
            confidence="heuristic",
        ),
        _edge(
            "COVERED_BY",
            nid("Function", "a"),
            nid("Test", "t"),
            provenance=Provenance.INFERRED,
            source="test-name-convention",
            confidence="heuristic",
        ),
    ]
    return nodes, edges


def _seed_item(key: str, rank: int) -> RankedItem:
    return RankedItem(
        evidence_id=nid("Function", key),
        strategy="lexical",
        rank=rank,
        score=1.0 / (rank + 1),
        target=EvidenceTarget(file="m.py", symbol=f"m.{key}", lines=(1, 2)),
        source_revision=REV,
        provenance=Provenance.OBSERVED,
        source="bm25",
    )


class FixedSeedStrategy:
    name = "lexical"

    def __init__(self, items: list[RankedItem]) -> None:
        self._items = items

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        items = [
            item.model_copy(update={"source_revision": query.revision}) for item in self._items
        ]
        return RetrievalResult(
            items=items,
            complete=True,
            strategy=self.name,
            revision=query.revision,
            elapsed_ms=0.0,
        )


class StubProvider:
    def __init__(
        self,
        result: Neighborhood | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.result = result or Neighborhood()
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def neighborhood(
        self,
        seed_ids: Any,
        *,
        revision: str,
        edge_types: Any = None,
        max_hops: int = 1,
        max_results: int = 100,
        timeout_ms: int = 1000,
    ) -> Neighborhood:
        self.calls.append(
            {
                "seed_ids": list(seed_ids),
                "revision": revision,
                "edge_types": edge_types,
                "max_hops": max_hops,
                "max_results": max_results,
                "timeout_ms": timeout_ms,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


def _query(
    text: str, *, max_items: int = 10, max_hops: int = 2, timeout_ms: int = 5000
) -> RetrievalQuery:
    return RetrievalQuery(
        case_id="c",
        text=text,
        revision=REV,
        k=max_items,
        limits=RetrievalLimits(max_items=max_items, max_hops=max_hops, timeout_ms=timeout_ms),
    )


def _strategy(
    provider: Any,
    seeds: list[RankedItem],
    **kwargs: Any,
) -> GraphGuidedStrategy:
    return GraphGuidedStrategy(provider, FixedSeedStrategy(seeds), **kwargs)  # type: ignore[arg-type]


def test_seeds_and_expansion_ordering() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1), _seed_item("b", 2)])
    result = strategy.retrieve(_query("anything"))
    assert [i.evidence_id for i in result.items] == [
        nid("Function", "a"),
        nid("Function", "b"),
        nid("Function", "c"),
        nid("Test", "t"),
        nid("Function", "d"),
    ]
    assert result.complete is True and result.strategy == "graph_guided"
    assert [i.rank for i in result.items] == [1, 2, 3, 4, 5]


def test_scores_are_monotonic_non_increasing() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1), _seed_item("b", 2)])
    result = strategy.retrieve(_query("anything"))
    scores = [i.score for i in result.items]
    assert scores == sorted(scores, reverse=True)


def test_seed_and_expansion_sources() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1)])
    result = strategy.retrieve(_query("anything"))
    by_id = {i.evidence_id: i for i in result.items}
    assert by_id[nid("Function", "a")].source == "graph_seed"
    assert by_id[nid("Function", "b")].source == "graph_callees"
    assert by_id[nid("Test", "t")].source == "graph_covered_by"


def test_inferred_edges_mark_items_inferred() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1)])
    result = strategy.retrieve(_query("anything"))
    by_id = {i.evidence_id: i for i in result.items}
    assert by_id[nid("Function", "b")].provenance is Provenance.OBSERVED
    assert by_id[nid("Function", "c")].provenance is Provenance.INFERRED
    assert by_id[nid("Test", "t")].provenance is Provenance.INFERRED


def test_duplicate_evidence_deduplicated() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1), _seed_item("b", 2)])
    result = strategy.retrieve(_query("anything"))
    ids = [i.evidence_id for i in result.items]
    assert len(ids) == len(set(ids))


def test_zero_hops_returns_seeds_only_complete() -> None:
    provider = StubProvider()
    strategy = _strategy(provider, [_seed_item("a", 1)])
    result = strategy.retrieve(_query("anything", max_hops=0))
    assert [i.evidence_id for i in result.items] == [nid("Function", "a")]
    assert result.complete is True
    assert provider.calls == []
    assert result.config["graph_status"] == "disabled"


def test_hop_limit_is_forwarded_and_result_limit_hits() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1), _seed_item("b", 2)])
    result = strategy.retrieve(_query("anything", max_items=3))
    assert len(result.items) == 3
    assert result.complete is False
    assert result.partial_reason is PartialReason.LIMIT_REACHED


def test_edge_type_filter_forwarded() -> None:
    nodes, edges = _snapshot()
    provider = StubProvider(Neighborhood())
    strategy = _strategy(provider, [_seed_item("a", 1)], edge_types=["CALLS"])
    strategy.retrieve(_query("anything"))
    assert provider.calls[0]["edge_types"] is not None
    assert list(provider.calls[0]["edge_types"]) == ["CALLS"]


def test_revision_mismatch_degrades_to_seeds() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1)])
    query = _query("anything").model_copy(update={"revision": "b" * 40})
    result = strategy.retrieve(query)
    assert result.complete is False
    assert result.partial_reason is PartialReason.GRAPH_UNAVAILABLE
    assert [i.evidence_id for i in result.items] == [nid("Function", "a")]
    assert result.config["graph_status"] == "revision_mismatch"


def test_unavailable_graph_degrades_to_seeds() -> None:
    provider = StubProvider(error=GraphUnavailableError("down"))
    strategy = _strategy(provider, [_seed_item("a", 1)])
    result = strategy.retrieve(_query("anything"))
    assert result.partial_reason is PartialReason.GRAPH_UNAVAILABLE
    assert [i.evidence_id for i in result.items] == [nid("Function", "a")]


def test_provider_error_recovered_to_seeds() -> None:
    provider = StubProvider(error=RuntimeError("boom"))
    strategy = _strategy(provider, [_seed_item("a", 1)])
    result = strategy.retrieve(_query("anything"))
    assert result.partial_reason is PartialReason.STRATEGY_ERROR_RECOVERED
    assert [i.evidence_id for i in result.items] == [nid("Function", "a")]
    assert result.config["graph_status"] == "provider_error"


def test_timeout_degrades_to_seeds() -> None:
    provider = StubProvider(Neighborhood(timed_out=True))
    strategy = _strategy(provider, [_seed_item("a", 1)])
    result = strategy.retrieve(_query("anything"))
    assert result.partial_reason is PartialReason.TIMEOUT
    assert [i.evidence_id for i in result.items] == [nid("Function", "a")]


def test_empty_seeds_returns_empty_complete() -> None:
    provider = StubProvider()
    strategy = _strategy(provider, [])
    result = strategy.retrieve(_query("anything"))
    assert result.items == []
    assert result.complete is True
    assert result.config["graph_status"] == "no_seeds"


def test_retrieval_is_deterministic() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1), _seed_item("b", 2)])
    first = strategy.retrieve(_query("anything"))
    second = strategy.retrieve(_query("anything"))
    assert [(i.evidence_id, i.rank, i.score) for i in first.items] == [
        (i.evidence_id, i.rank, i.score) for i in second.items
    ]


def test_explanations_expose_graph_path() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1)])
    strategy.retrieve(_query("anything"))
    path = strategy.explain(nid("Function", "c"))
    assert isinstance(path, GraphPath)
    assert path.depth == 1 and path.node_ids == (nid("Function", "a"), nid("Function", "c"))
    assert strategy.explain(nid("Function", "a")) is None


def test_truncated_expansion_reports_limit_reached() -> None:
    nodes, edges = _snapshot()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    strategy = _strategy(provider, [_seed_item("a", 1), _seed_item("b", 2)])
    result = strategy.retrieve(_query("anything", max_items=10, max_hops=2))
    provider_stub = StubProvider(Neighborhood(paths=(), truncated=True))
    truncating = _strategy(provider_stub, [_seed_item("a", 1)])
    truncated = truncating.retrieve(_query("anything"))
    assert result.complete is True
    assert truncated.partial_reason is PartialReason.LIMIT_REACHED


def test_seed_strategy_failure_propagates() -> None:
    provider = StubProvider(error=GraphUnavailableError("down"))

    class ExplodingSeeds(FixedSeedStrategy):
        def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
            raise RetrievalError("seed failure")

    strategy = GraphGuidedStrategy(provider, ExplodingSeeds([]))  # type: ignore[arg-type]
    with pytest.raises(RetrievalError):
        strategy.retrieve(_query("anything"))


def test_integration_with_lexical_seeds(mini_repo: Path, mini_repo_url: str) -> None:
    ingested = ingest_repository(mini_repo, mini_repo_url, ingested_at="2026-10-16T00:00:00+00:00")
    corpus = build_function_corpus(mini_repo, ingested.nodes)
    lexical = LexicalBM25Strategy(corpus)
    provider = SnapshotNeighborhoodProvider(ingested.nodes, ingested.edges, direction="out")
    strategy = GraphGuidedStrategy(provider, lexical, seed_count=3)
    query = RetrievalQuery(
        case_id="c",
        text="accumulate values loop total",
        revision=ingested.revision,
        k=5,
        limits=RetrievalLimits(max_items=10, max_hops=1, timeout_ms=5000),
    )
    result = strategy.retrieve(query)
    assert result.items[0].target.symbol == "calc.core.accumulate"
    assert result.items[0].source == "graph_seed"
    ids = [i.evidence_id for i in result.items]
    assert len(ids) == len(set(ids))
    assert result.complete or result.partial_reason is not None

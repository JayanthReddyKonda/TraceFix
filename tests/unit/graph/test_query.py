"""Typed graph-query + bounded-expansion provider tests (A2.1-A2.3, A3.3).

All service-free: the snapshot provider runs in memory; the FalkorDB provider is
exercised with a recording stub client. Live-server behavior is unverified (D6).
"""

from __future__ import annotations

from typing import Any

import pytest

from tracefix.graph.client import GraphConnectionError, GraphTimeoutError
from tracefix.graph.models import Edge, Node, Provenance
from tracefix.graph.query import (
    DIRECTION_PATTERN,
    FalkorNeighborhoodProvider,
    GraphQuery,
    GraphRevisionMismatchError,
    GraphUnavailableError,
    SnapshotNeighborhoodProvider,
    build_neighborhood_cypher,
)

REV = "a" * 40
REPO = "https://example.test/repo"


def nid(kind: str, key: str) -> str:
    return f"{REPO}#{kind}:{key}"


def node(kind: str, key: str, *, revision: str = REV, **props: Any) -> Node:
    return Node(
        entity_id=nid(kind, key),
        kind=kind,
        repo=REPO,
        revision=revision,
        properties=dict(props),
        ingested_at="2026-10-16T00:00:00+00:00",
    )


def edge(
    edge_type: str,
    source_id: str,
    target_id: str,
    *,
    provenance: Provenance = Provenance.OBSERVED,
    source: str = "python-ast",
    confidence: str | None = None,
    revision: str = REV,
) -> Edge:
    return Edge(
        edge_type=edge_type,
        source_id=source_id,
        target_id=target_id,
        provenance=provenance,
        source=source,
        revision=revision,
        confidence=confidence,
    )


def _sym(
    key: str, path: str, start: int, end: int, *, kind: str = "Function", suffix: str = "m"
) -> Node:
    return node(
        kind, key, path=path, qualified_name=f"{suffix}.{key}", start_line=start, end_line=end
    )


def _graph() -> tuple[dict[str, Node], list[Edge]]:
    """a -> b (observed), b -> d (observed), a -> c (inferred), a COVERED_BY t."""
    nodes = {
        nid("Function", "a"): _sym("a", "m.py", 1, 2),
        nid("Function", "b"): _sym("b", "m.py", 4, 5),
        nid("Function", "c"): _sym("c", "m.py", 7, 8),
        nid("Function", "d"): _sym("d", "n.py", 1, 2, suffix="n"),
        nid("Test", "t"): _sym("t", "tests/test_m.py", 1, 2, kind="Test", suffix="tests.test_m"),
    }
    edges = [
        edge("CALLS", nid("Function", "a"), nid("Function", "b"), source="name-resolution"),
        edge("CALLS", nid("Function", "b"), nid("Function", "d"), source="name-resolution"),
        edge(
            "CALLS",
            nid("Function", "a"),
            nid("Function", "c"),
            provenance=Provenance.INFERRED,
            source="name-heuristic",
            confidence="heuristic",
        ),
        edge(
            "COVERED_BY",
            nid("Function", "a"),
            nid("Test", "t"),
            provenance=Provenance.INFERRED,
            source="test-name-convention",
            confidence="heuristic",
        ),
    ]
    return nodes, edges


# ------------------------------------------------------------------ snapshot


def test_zero_hops_returns_no_paths() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges)
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=0)
    assert result.paths == ()
    assert result.truncated is False and result.timed_out is False


def test_one_hop_out_collects_callees() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    result = provider.neighborhood(
        [nid("Function", "a")], revision=REV, edge_types=["CALLS"], max_hops=1
    )
    reached = {p.node.entity_id for p in result.paths}
    assert reached == {nid("Function", "b"), nid("Function", "c")}
    assert all(p.depth == 1 for p in result.paths)


def test_one_hop_in_collects_callers() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="in")
    result = provider.neighborhood([nid("Function", "b")], revision=REV, max_hops=1)
    assert {p.node.entity_id for p in result.paths} == {nid("Function", "a")}


def test_multi_hop_reaches_depth_two() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=2)
    by_depth = {p.node.entity_id: p.depth for p in result.paths}
    assert by_depth[nid("Function", "b")] == 1
    assert by_depth[nid("Function", "d")] == 2


def test_hop_limit_bounds_expansion() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=1)
    assert nid("Function", "d") not in {p.node.entity_id for p in result.paths}


def test_result_limit_sets_truncated() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="both")
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=2, max_results=1)
    assert len(result.paths) == 1
    assert result.truncated is True


def test_edge_type_filter() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    result = provider.neighborhood(
        [nid("Function", "a")], revision=REV, edge_types=["CALLS"], max_hops=2
    )
    assert {p.node.entity_id for p in result.paths} == {
        nid("Function", "b"),
        nid("Function", "c"),
        nid("Function", "d"),
    }


def test_duplicate_node_reached_once_via_first_seed() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    result = provider.neighborhood(
        [nid("Function", "a"), nid("Function", "b")], revision=REV, max_hops=1
    )
    ids = [p.node.entity_id for p in result.paths]
    assert len(ids) == len(set(ids))
    d_path = next(p for p in result.paths if p.node.entity_id == nid("Function", "d"))
    assert d_path.origin_seed_id == nid("Function", "b")


def test_inferred_path_exposes_provenance_and_label() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    result = provider.neighborhood(
        [nid("Function", "a")], revision=REV, edge_types=["COVERED_BY"], max_hops=1
    )
    path = result.paths[0]
    assert path.provenance is Provenance.INFERRED
    assert path.confidence == "heuristic"
    assert path.source_label == "graph_covered_by"
    assert path.node_ids == (nid("Function", "a"), nid("Test", "t"))


def test_observed_path_label_for_calls_out_and_in() -> None:
    nodes, edges = _graph()
    out = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    callee = out.neighborhood(
        [nid("Function", "a")], revision=REV, edge_types=["CALLS"], max_hops=1
    )
    labels = {p.node.entity_id: p.source_label for p in callee.paths}
    assert labels[nid("Function", "b")] == "graph_callees"
    into = SnapshotNeighborhoodProvider(nodes, edges, direction="in")
    caller = into.neighborhood(
        [nid("Function", "b")], revision=REV, edge_types=["CALLS"], max_hops=1
    )
    assert caller.paths[0].source_label == "graph_callers"


def test_revision_mismatch_raises() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges)
    with pytest.raises(GraphRevisionMismatchError):
        provider.neighborhood([nid("Function", "a")], revision="b" * 40, max_hops=1)


def test_mixed_revision_snapshot_rejected_at_construction() -> None:
    nodes, edges = _graph()
    nodes[nid("Function", "z")] = node("Function", "z", revision="c" * 40)
    with pytest.raises(GraphRevisionMismatchError):
        SnapshotNeighborhoodProvider(nodes, edges)


def test_timeout_via_injected_clock() -> None:
    nodes, edges = _graph()
    ticks = iter([0.0, 100.0])
    provider = SnapshotNeighborhoodProvider(
        nodes, edges, direction="out", clock=lambda: next(ticks)
    )
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=1, timeout_ms=10)
    assert result.timed_out is True
    assert result.paths == ()


def test_empty_seeds_returns_empty() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges)
    assert provider.neighborhood([], revision=REV, max_hops=2).paths == ()


def test_unknown_seed_id_is_ignored() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges)
    seed = nid("Function", "ghost")
    result = provider.neighborhood(
        [seed, nid("Function", "a")], revision=REV, edge_types=["CALLS"], max_hops=1
    )
    assert {p.node.entity_id for p in result.paths} == {nid("Function", "b"), nid("Function", "c")}


def test_ordering_is_deterministic() -> None:
    nodes, edges = _graph()
    provider = SnapshotNeighborhoodProvider(nodes, edges, direction="out")
    first = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=2)
    second = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=2)
    assert [p.node.entity_id for p in first.paths] == [p.node.entity_id for p in second.paths]


# --------------------------------------------------------------------- cypher


def test_build_cypher_injects_literal_bound_and_direction() -> None:
    cypher = build_neighborhood_cypher(3, "in")
    assert "<-[*1..3]-" in cypher
    assert "$seed_ids" in cypher and "$revision" in cypher and "$max_results" in cypher
    assert "$edge_types" in cypher


@pytest.mark.parametrize("bad", [0, -1, True])
def test_build_cypher_rejects_bad_hops(bad: object) -> None:
    with pytest.raises(ValueError):
        build_neighborhood_cypher(bad, "out")  # type: ignore[arg-type]


def test_build_cypher_rejects_bad_direction() -> None:
    with pytest.raises(ValueError):
        build_neighborhood_cypher(1, "sideways")
    assert set(DIRECTION_PATTERN) == {"out", "in", "both"}


# ----------------------------------------------------------- falkor provider


class StubClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def execute(
        self, cypher: str, params: dict[str, Any] | None = None, timeout_ms: int | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append({"cypher": cypher, "params": params, "timeout": timeout_ms})
        if self.error is not None:
            raise self.error
        return self.rows


def _path_row() -> dict[str, Any]:
    return {
        "entity_id": nid("Function", "b"),
        "kind": "Function",
        "path": "m.py",
        "qualified_name": "m.b",
        "start_line": 4,
        "end_line": 5,
        "revision": REV,
        "depth": 1,
        "path_ids": [nid("Function", "a"), nid("Function", "b")],
        "edge_sources": [nid("Function", "a")],
        "edge_targets": [nid("Function", "b")],
        "edge_types": ["CALLS"],
        "edge_provenances": ["observed"],
        "edge_sources_names": ["name-resolution"],
        "edge_confidences": [None],
    }


def test_falkor_provider_binds_params_and_parses_rows() -> None:
    client = StubClient([_path_row()])
    provider = FalkorNeighborhoodProvider(client, direction="out")  # type: ignore[arg-type]
    result = provider.neighborhood(
        [nid("Function", "a")], revision=REV, edge_types=["CALLS"], max_hops=2, timeout_ms=250
    )
    call = client.calls[0]
    assert call["params"] == {
        "seed_ids": [nid("Function", "a")],
        "revision": REV,
        "edge_types": ["CALLS"],
        "max_results": 100,
    }
    assert call["timeout"] == 250
    assert "-[*1..2]->" in call["cypher"]
    assert len(result.paths) == 1
    path = result.paths[0]
    assert path.node.entity_id == nid("Function", "b")
    assert path.origin_seed_id == nid("Function", "a")
    assert path.edges[0].provenance is Provenance.OBSERVED
    assert path.source_label == "graph_callees"


def test_falkor_provider_zero_hops_skips_query() -> None:
    client = StubClient([_path_row()])
    provider = FalkorNeighborhoodProvider(client)  # type: ignore[arg-type]
    assert provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=0).paths == ()
    assert client.calls == []


def test_falkor_provider_connection_error_is_typed() -> None:
    client = StubClient(error=GraphConnectionError("down"))
    provider = FalkorNeighborhoodProvider(client)  # type: ignore[arg-type]
    with pytest.raises(GraphUnavailableError):
        provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=1)


def test_falkor_provider_timeout_returns_partial() -> None:
    client = StubClient(error=GraphTimeoutError("slow"))
    provider = FalkorNeighborhoodProvider(client)  # type: ignore[arg-type]
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=1)
    assert result.timed_out is True and result.paths == ()


def test_falkor_provider_truncation_flag() -> None:
    client = StubClient([_path_row(), _path_row()])
    provider = FalkorNeighborhoodProvider(client)  # type: ignore[arg-type]
    result = provider.neighborhood([nid("Function", "a")], revision=REV, max_hops=1, max_results=2)
    assert result.truncated is True


# ------------------------------------------------------------- typed operations


def _node_row(key: str) -> dict[str, Any]:
    return {
        "entity_id": nid("Function", key),
        "kind": "Function",
        "path": "m.py",
        "qualified_name": f"m.{key}",
        "start_line": 1,
        "end_line": 2,
        "revision": REV,
    }


def test_find_symbols_is_parameterized() -> None:
    client = StubClient([_node_row("a")])
    query = GraphQuery(client)  # type: ignore[arg-type]
    result = query.find_symbols(REV, "m.a")
    assert [n.entity_id for n in result] == [nid("Function", "a")]
    params = client.calls[0]["params"]
    assert params == {"revision": REV, "qualified_name": "m.a"}
    assert "$qualified_name" in client.calls[0]["cypher"]


def test_definitions_imports_covering_commits_use_placeholders() -> None:
    client = StubClient([_node_row("a")])
    query = GraphQuery(client)  # type: ignore[arg-type]
    query.definitions_in_file(REV, "m.py")
    query.imports_of_module(REV, nid("Module", "m"))
    query.covering_tests(REV, nid("Function", "a"))
    query.commits_for_file(REV, "m.py")
    for call in client.calls:
        assert call["params"]["revision"] == REV
        assert "$revision" in call["cypher"]
        assert "MATCH" in call["cypher"]
    assert client.calls[0]["params"]["path"] == "m.py"
    assert client.calls[1]["params"]["module_id"] == nid("Module", "m")
    assert client.calls[2]["params"]["function_id"] == nid("Function", "a")
    assert client.calls[3]["params"]["path"] == "m.py"

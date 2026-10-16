"""Typed graph query layer (A2.1-A2.3) and bounded-expansion provider (A3.3).

Retrieval callers never build or see Cypher: they use the typed operations here
(parameterized internally) or the `NeighborhoodProvider` protocol, which returns
typed `GraphPath` records that preserve provenance (observed/inferred) and the
traversal path.

Two providers implement `NeighborhoodProvider`:

- `SnapshotNeighborhoodProvider` — in-memory BFS over an ingestion snapshot
  (`nodes`, `edges`). Deterministic, no infrastructure, used by unit tests and
  offline runs.
- `FalkorNeighborhoodProvider` — runs parameterized Cypher through the
  `FalkorDBClient`. Hop bounds are injected as a validated integer literal
  (Cypher forbids parameters in variable-length path bounds); all other values
  are bound parameters. **Live-server behavior is unverified** (Docker down,
  D6); only query construction and row parsing are unit-tested.

Limits enforced at this layer: hop count, result count, and a wall-clock
deadline. A revision constraint is enforced on every seed and reached node.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from tracefix.graph.client import FalkorDBClient, GraphConnectionError, GraphTimeoutError
from tracefix.graph.models import Edge, Node, Provenance

NEIGHBOREDGE_TYPES_ALL: tuple[str, ...] = ()


class GraphExpansionError(Exception):
    """Base class for typed graph-query/expansion failures."""


class GraphUnavailableError(GraphExpansionError):
    """The graph could not serve the request (connection, query, or missing data)."""


class GraphRevisionMismatchError(GraphExpansionError):
    """The provider's data revision does not match the requested revision."""


@dataclass(frozen=True)
class NeighborNode:
    entity_id: str
    kind: str
    path: str | None
    qualified_name: str | None
    start_line: int | None
    end_line: int | None
    revision: str


@dataclass(frozen=True)
class GraphEdgeRef:
    edge_type: str
    source_id: str
    target_id: str
    direction: str  # "out" | "in" relative to traversal from source to target
    provenance: Provenance
    source: str
    confidence: str | None


@dataclass(frozen=True)
class GraphPath:
    depth: int
    origin_seed_id: str
    edges: tuple[GraphEdgeRef, ...]
    node: NeighborNode

    @property
    def node_ids(self) -> tuple[str, ...]:
        ids = [self.origin_seed_id]
        current = self.origin_seed_id
        for edge in self.edges:
            current = edge.target_id if edge.direction == "out" else edge.source_id
            ids.append(current)
        return tuple(ids)

    @property
    def provenance(self) -> Provenance:
        if any(edge.provenance is Provenance.INFERRED for edge in self.edges):
            return Provenance.INFERRED
        return Provenance.OBSERVED

    @property
    def confidence(self) -> str | None:
        return "heuristic" if self.provenance is Provenance.INFERRED else None

    @property
    def source_label(self) -> str:
        if not self.edges:
            return "graph_seed"
        last = self.edges[-1]
        if last.edge_type == "CALLS":
            return "graph_callers" if last.direction == "in" else "graph_callees"
        return f"graph_{last.edge_type.lower()}"


@dataclass(frozen=True)
class Neighborhood:
    paths: tuple[GraphPath, ...] = ()
    truncated: bool = False
    timed_out: bool = False


@runtime_checkable
class NeighborhoodProvider(Protocol):
    def neighborhood(
        self,
        seed_ids: Sequence[str],
        *,
        revision: str,
        edge_types: Sequence[str] | None = None,
        max_hops: int = 1,
        max_results: int = 100,
        timeout_ms: int = 1000,
    ) -> Neighborhood: ...


def node_to_neighbor(node: Node) -> NeighborNode:
    props = node.properties
    return NeighborNode(
        entity_id=node.entity_id,
        kind=node.kind,
        path=_opt_str(props.get("path")),
        qualified_name=_opt_str(props.get("qualified_name")),
        start_line=_opt_int(props.get("start_line")),
        end_line=_opt_int(props.get("end_line")),
        revision=node.revision,
    )


def _opt_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _opt_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class SnapshotNeighborhoodProvider:
    """In-memory bounded BFS over one ingestion snapshot.

    `direction` is "out", "in", or "both". The provider is bound to the snapshot
    the nodes/edges were extracted from; requesting any other revision raises
    `GraphRevisionMismatchError`.
    """

    def __init__(
        self,
        nodes: dict[str, Node] | Sequence[Node],
        edges: Sequence[Edge],
        *,
        direction: str = "both",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if direction not in ("out", "in", "both"):
            raise ValueError(f"invalid direction {direction!r}")
        self.direction = direction
        self._clock = clock
        self._nodes: dict[str, Node] = (
            dict(nodes) if isinstance(nodes, dict) else {n.entity_id: n for n in nodes}
        )
        self._edges: list[Edge] = list(edges)
        if self._nodes:
            revisions = {n.revision for n in self._nodes.values()}
            if len(revisions) > 1:
                raise GraphRevisionMismatchError("snapshot mixes multiple revisions")
            self.revision: str | None = next(iter(revisions))
        else:
            self.revision = None

    def _adjacency(self, edge_types: Sequence[str] | None) -> dict[str, list[tuple[Edge, str]]]:
        allowed = set(edge_types) if edge_types else None
        adjacency: dict[str, list[tuple[Edge, str]]] = {}
        for edge in self._edges:
            if allowed is not None and edge.edge_type not in allowed:
                continue
            if self.direction in ("out", "both"):
                adjacency.setdefault(edge.source_id, []).append((edge, "out"))
            if self.direction in ("in", "both"):
                adjacency.setdefault(edge.target_id, []).append((edge, "in"))
        for key in adjacency:
            adjacency[key].sort(
                key=lambda pair: (
                    pair[0].edge_type,
                    pair[1],
                    pair[0].source_id,
                    pair[0].target_id,
                )
            )
        return adjacency

    def neighborhood(
        self,
        seed_ids: Sequence[str],
        *,
        revision: str,
        edge_types: Sequence[str] | None = None,
        max_hops: int = 1,
        max_results: int = 100,
        timeout_ms: int = 1000,
    ) -> Neighborhood:
        if max_hops < 0:
            raise ValueError("max_hops must be >= 0")
        if max_results < 0:
            raise ValueError("max_results must be >= 0")
        if self.revision is not None and revision != self.revision:
            raise GraphRevisionMismatchError(
                f"provider snapshot is at {self.revision}, requested {revision}"
            )
        for seed in seed_ids:
            node = self._nodes.get(seed)
            if node is not None and node.revision != revision:
                raise GraphRevisionMismatchError(
                    f"seed {seed} is at {node.revision}, requested {revision}"
                )

        deadline = self._clock() + timeout_ms / 1000.0
        adjacency = self._adjacency(edge_types)
        paths: list[GraphPath] = []
        timed_out = False
        truncated = False
        visited: set[str] = set(seed_ids)
        frontier: list[tuple[str, str, tuple[GraphEdgeRef, ...]]] = [
            (seed, seed, ()) for seed in seed_ids if seed in self._nodes
        ]
        for _ in range(max_hops):
            next_frontier: list[tuple[str, str, tuple[GraphEdgeRef, ...]]] = []
            for current_id, origin, trail in frontier:
                for edge, direction in adjacency.get(current_id, []):
                    neighbor_id = edge.target_id if direction == "out" else edge.source_id
                    if neighbor_id in visited:
                        continue
                    if self._clock() > deadline:
                        timed_out = True
                        break
                    neighbor = self._nodes.get(neighbor_id)
                    if neighbor is None or neighbor.revision != revision:
                        continue
                    visited.add(neighbor_id)
                    ref = GraphEdgeRef(
                        edge_type=edge.edge_type,
                        source_id=edge.source_id,
                        target_id=edge.target_id,
                        direction=direction,
                        provenance=edge.provenance,
                        source=edge.source,
                        confidence=edge.confidence,
                    )
                    new_trail = trail + (ref,)
                    paths.append(
                        GraphPath(
                            depth=len(new_trail),
                            origin_seed_id=origin,
                            edges=new_trail,
                            node=node_to_neighbor(neighbor),
                        )
                    )
                    next_frontier.append((neighbor_id, origin, new_trail))
                    if len(paths) >= max_results:
                        truncated = True
                        break
                if timed_out or truncated:
                    break
            if timed_out or truncated:
                break
            frontier = next_frontier
            if not frontier:
                break
        return Neighborhood(paths=tuple(paths), truncated=truncated, timed_out=timed_out)


DIRECTION_PATTERN = {
    "out": "`-[*1..{h}]->`",
    "in": "`<-[*1..{h}]-`",
    "both": "`-[*1..{h}]-`",
}


def build_neighborhood_cypher(max_hops: int, direction: str) -> str:
    """Return the parameterized Cypher for a bounded neighborhood.

    `max_hops` is validated here and injected as an integer literal because
    Cypher does not allow parameters inside variable-length path bounds. No
    caller-supplied string reaches the query.
    """
    if not isinstance(max_hops, int) or isinstance(max_hops, bool) or max_hops < 1:
        raise ValueError("max_hops must be an int >= 1")
    if direction not in DIRECTION_PATTERN:
        raise ValueError(f"invalid direction {direction!r}")
    pattern = DIRECTION_PATTERN[direction].format(h=max_hops).strip("`")
    return (
        f"MATCH path = (seed){pattern}(m) "
        "WHERE seed.entity_id IN $seed_ids AND seed.revision = $revision "
        "AND m.revision = $revision "
        "AND all(r IN relationships(path) WHERE r.revision = $revision "
        "AND (size($edge_types) = 0 OR type(r) IN $edge_types)) "
        "RETURN m.entity_id AS entity_id, m.kind AS kind, m.path AS path, "
        "m.qualified_name AS qualified_name, m.start_line AS start_line, "
        "m.end_line AS end_line, m.revision AS revision, "
        "length(path) AS depth, [n IN nodes(path) | n.entity_id] AS path_ids, "
        "[r IN relationships(path) | startNode(r).entity_id] AS edge_sources, "
        "[r IN relationships(path) | endNode(r).entity_id] AS edge_targets, "
        "[r IN relationships(path) | type(r)] AS edge_types, "
        "[r IN relationships(path) | r.provenance] AS edge_provenances, "
        "[r IN relationships(path) | r.source] AS edge_sources_names, "
        "[r IN relationships(path) | r.confidence] AS edge_confidences "
        "ORDER BY depth, entity_id LIMIT $max_results"
    )


class FalkorNeighborhoodProvider:
    """Bounded expansion executed through `FalkorDBClient` (unverified live)."""

    def __init__(self, client: FalkorDBClient, *, direction: str = "both") -> None:
        if direction not in DIRECTION_PATTERN:
            raise ValueError(f"invalid direction {direction!r}")
        self.client = client
        self.direction = direction

    def neighborhood(
        self,
        seed_ids: Sequence[str],
        *,
        revision: str,
        edge_types: Sequence[str] | None = None,
        max_hops: int = 1,
        max_results: int = 100,
        timeout_ms: int = 1000,
    ) -> Neighborhood:
        if max_hops == 0 or not seed_ids:
            return Neighborhood()
        cypher = build_neighborhood_cypher(max_hops, self.direction)
        params = {
            "seed_ids": list(seed_ids),
            "revision": revision,
            "edge_types": list(edge_types or []),
            "max_results": max_results,
        }
        try:
            rows = self.client.execute(cypher, params=params, timeout_ms=timeout_ms)
        except GraphTimeoutError:
            return Neighborhood(timed_out=True)
        except GraphConnectionError as exc:
            raise GraphUnavailableError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - mapped to typed error by design
            raise GraphUnavailableError(f"graph query failed: {exc}") from exc
        paths = [_row_to_path(row) for row in rows]
        truncated = len(paths) >= max_results
        return Neighborhood(paths=tuple(p for p in paths if p is not None), truncated=truncated)


def _row_to_path(row: dict[str, Any]) -> GraphPath | None:
    node = NeighborNode(
        entity_id=str(row["entity_id"]),
        kind=str(row.get("kind", "")),
        path=_opt_str(row.get("path")),
        qualified_name=_opt_str(row.get("qualified_name")),
        start_line=_opt_int(row.get("start_line")),
        end_line=_opt_int(row.get("end_line")),
        revision=str(row.get("revision", "")),
    )
    edge_types = list(row.get("edge_types") or [])
    provenances = list(row.get("edge_provenances") or [])
    sources = list(row.get("edge_sources_names") or [])
    confidences = list(row.get("edge_confidences") or [])
    edge_sources = list(row.get("edge_sources") or [])
    edge_targets = list(row.get("edge_targets") or [])
    path_ids = list(row.get("path_ids") or [])
    depth = int(row.get("depth") or len(edge_types))
    if not path_ids or depth < 1:
        return None
    origin_seed_id = str(path_ids[0])
    refs: list[GraphEdgeRef] = []
    for index in range(depth):
        src = str(edge_sources[index])
        tgt = str(edge_targets[index])
        direction = "out" if path_ids[index] == src and path_ids[index + 1] == tgt else "in"
        provenance = (
            Provenance(provenances[index]) if index < len(provenances) else Provenance.OBSERVED
        )
        refs.append(
            GraphEdgeRef(
                edge_type=str(edge_types[index]),
                source_id=src,
                target_id=tgt,
                direction=direction,
                provenance=provenance,
                source=str(sources[index]) if index < len(sources) else "graph",
                confidence=_opt_str(confidences[index]) if index < len(confidences) else None,
            )
        )
    return GraphPath(depth=depth, origin_seed_id=origin_seed_id, edges=tuple(refs), node=node)


class GraphQuery:
    """Typed, parameterized graph operations (A2.1). No caller supplies Cypher.

    Every method filters by the snapshot `revision` so a query can never read a
    different revision's entities. Failures surface the typed client errors.
    """

    _NODE_COLUMNS = (
        "n.entity_id AS entity_id, n.kind AS kind, n.path AS path, "
        "n.qualified_name AS qualified_name, n.start_line AS start_line, "
        "n.end_line AS end_line, n.revision AS revision"
    )

    def __init__(self, client: FalkorDBClient) -> None:
        self.client = client

    def find_symbols(
        self, revision: str, qualified_name: str, *, timeout_ms: int | None = None
    ) -> list[NeighborNode]:
        cypher = (
            f"MATCH (n {{revision: $revision, qualified_name: $qualified_name}}) "
            f"RETURN {self._NODE_COLUMNS} ORDER BY n.kind, n.entity_id"
        )
        return self._nodes(
            cypher, {"revision": revision, "qualified_name": qualified_name}, timeout_ms
        )

    def definitions_in_file(
        self, revision: str, path: str, *, timeout_ms: int | None = None
    ) -> list[NeighborNode]:
        cypher = (
            "MATCH (n {revision: $revision, path: $path}) "
            "WHERE n.kind IN ['Module', 'Class', 'Function', 'Test'] "
            f"RETURN {self._NODE_COLUMNS} ORDER BY n.start_line, n.entity_id"
        )
        return self._nodes(cypher, {"revision": revision, "path": path}, timeout_ms)

    def imports_of_module(
        self, revision: str, module_id: str, *, timeout_ms: int | None = None
    ) -> list[NeighborNode]:
        cypher = (
            "MATCH (m:Module {revision: $revision, entity_id: $module_id})-[:IMPORTS]->(n) "
            "WHERE n.revision = $revision "
            f"RETURN {self._NODE_COLUMNS} ORDER BY n.entity_id"
        )
        return self._nodes(cypher, {"revision": revision, "module_id": module_id}, timeout_ms)

    def covering_tests(
        self, revision: str, function_id: str, *, timeout_ms: int | None = None
    ) -> list[NeighborNode]:
        cypher = (
            "MATCH (f:Function {revision: $revision, entity_id: $function_id})"
            "-[:COVERED_BY]->(n:Test) WHERE n.revision = $revision "
            f"RETURN {self._NODE_COLUMNS} ORDER BY n.entity_id"
        )
        return self._nodes(cypher, {"revision": revision, "function_id": function_id}, timeout_ms)

    def commits_for_file(
        self, revision: str, path: str, *, timeout_ms: int | None = None
    ) -> list[NeighborNode]:
        cypher = (
            "MATCH (f:File {revision: $revision, path: $path})-[:MODIFIED_IN]->(n:Commit) "
            "WHERE n.revision = $revision "
            f"RETURN {self._NODE_COLUMNS} ORDER BY n.committed_at DESC, n.entity_id"
        )
        return self._nodes(cypher, {"revision": revision, "path": path}, timeout_ms)

    def _nodes(
        self, cypher: str, params: dict[str, Any], timeout_ms: int | None
    ) -> list[NeighborNode]:
        rows = self.client.execute(cypher, params=params, timeout_ms=timeout_ms)
        return [_row_to_node(row) for row in rows]


def _row_to_node(row: dict[str, Any]) -> NeighborNode:
    return NeighborNode(
        entity_id=str(row["entity_id"]),
        kind=str(row.get("kind", "")),
        path=_opt_str(row.get("path")),
        qualified_name=_opt_str(row.get("qualified_name")),
        start_line=_opt_int(row.get("start_line")),
        end_line=_opt_int(row.get("end_line")),
        revision=str(row.get("revision", "")),
    )

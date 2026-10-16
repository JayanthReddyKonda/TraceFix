# Graph query layer (A2.1–A2.3) and bounded expansion (A3.3)

`src/tracefix/graph/query.py` — the only module retrieval callers use to touch
the graph. Callers never build or see Cypher; every entry point filters by the
snapshot revision and validates inputs before they reach the database.

## Typed operations (A2.1)

`GraphQuery(client)` exposes typed, parameterized reads:

| Method | Returns | Backing match |
|---|---|---|
| `find_symbols(revision, qualified_name)` | `list[NeighborNode]` | nodes by `qualified_name` |
| `definitions_in_file(revision, path)` | `list[NeighborNode]` | `Module/Class/Function/Test` by `path` |
| `imports_of_module(revision, module_id)` | `list[NeighborNode]` | `Module-[:IMPORTS]->n` |
| `covering_tests(revision, function_id)` | `list[NeighborNode]` | `Function-[:COVERED_BY]->Test` |
| `commits_for_file(revision, path)` | `list[NeighborNode]` | `File-[:MODIFIED_IN]->Commit` |

Every query binds `$revision` and constrains both endpoints to it; there is no
string interpolation of caller values. Failures surface the typed client errors
(`GraphConnectionError`, `GraphTimeoutError`, `GraphQueryError`).

## Bounded expansion (A3.3)

`NeighborhoodProvider` is a runtime-checkable protocol:

```python
neighborhood(seed_ids, *, revision, edge_types=None,
             max_hops=1, max_results=100, timeout_ms=1000) -> Neighborhood
```

`Neighborhood` carries `paths: tuple[GraphPath, ...]`, `truncated`, `timed_out`.
Each `GraphPath` records `depth`, `origin_seed_id`, the ordered `edges`
(`GraphEdgeRef` joins, each with `provenance`/`source`/`confidence`), and the
reached `node`. Derived properties: `node_ids`, `provenance` (inferred if any
edge is inferred), `confidence`, and `source_label` (`graph_seed`,
`graph_callers`, `graph_callees`, `graph_covered_by`, …).

Limits enforced here: hop count, result count, and a wall-clock deadline.
Revision is enforced on every seed and reached node.

### Providers

- **`SnapshotNeighborhoodProvider`** — deterministic in-memory BFS over an
  ingestion snapshot (`nodes`, `edges`), `direction` in `out|in|both`, no
  infrastructure. Unknown seed ids are ignored; a node reached by several seeds
  is emitted once, attributed to the first origin in seed order. Construction
  rejects a snapshot mixing revisions; querying a different revision (or a seed
  at a different revision) raises `GraphRevisionMismatchError`. The clock is
  injectable for deterministic timeout tests.
- **`FalkorNeighborhoodProvider`** — runs parameterized Cypher through
  `FalkorDBClient`. `GraphTimeoutError` → `Neighborhood(timed_out=True)`;
  `GraphConnectionError`/other → `GraphUnavailableError`; `max_hops == 0` or no
  seeds short-circuits without querying. `truncated` is set when rows reach
  `max_results`.

## Hop-bound injection

Cypher forbids parameters inside variable-length path bounds
(`-[*1..$h]->`), so `build_neighborhood_cypher(max_hops, direction)` validates
`max_hops` (a positive non-bool `int`) and injects it as a literal; the
direction is chosen from a fixed `DIRECTION_PATTERN` map. All other values —
`seed_ids`, `revision`, `edge_types`, `max_results` — are bound parameters. No
caller-supplied string reaches the query text.

## Limitations / unverified

**Live FalkorDB behavior is unverified** (Docker daemon down; D6). Only query
construction and row parsing are covered by tests, using a recording stub
client. Live acceptance remains A2.4, blocked.

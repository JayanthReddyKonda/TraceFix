# Graph-guided retrieval (A3.3)

`src/tracefix/retrieval/graph_guided.py` — `GraphGuidedStrategy`, a C2
`RetrievalStrategy` that expands lexical seeds along the graph behind the typed
`NeighborhoodProvider` interface. It makes **no** arbitrary Cypher available and
does not change the retrieval contract.

## Pipeline

1. Retrieve lexical seeds (`LexicalBM25Strategy`) — `seed_count` seeds, capped by
   `limits.max_items`.
2. If `limits.max_hops >= 1`, ask the provider for a bounded neighborhood of the
   seed ids (edge types configurable, `max_results = max_items * fanout`).
3. Merge, dedup by `evidence_id`, and rerank deterministically.

## Ranking and determinism

Candidates are ordered by `(depth, seed_rank, evidence_id)` ascending: seeds are
depth 0, then expansions by hop distance, then by the rank of the seed that
reached them, then by stable id. `score = 1/(depth+1) + 1/(seed_rank+1)` is
monotonic with that order. Ranks are dense and 1-based (`RetrievalResult`
enforces this). Ties never depend on iteration order.

Expanded items are deduplicated against the seeds and against each other: a node
that is both a seed and reachable keeps its seed entry.

## Provenance and explanations

Each item keeps its provenance: an expanded item is `provenance=inferred` if any
edge on its path is inferred, `observed` otherwise. `source` labels the
traversal (`graph_seed`, `graph_callers`, `graph_callees`, `graph_covered_by`,
…). The structured `GraphPath` for each expanded item is retained for the
(draft) context manifest and exposed via `strategy.explain(evidence_id)`; the C2
`RankedItem` itself is unchanged.

## Degradation (C2 failure semantics)

| Situation | Result |
|---|---|
| graph unavailable / revision mismatch | seeds returned, `partial_reason=graph_unavailable` |
| other provider error | seeds returned, `partial_reason=strategy_error_recovered` |
| `timed_out` or wall-clock over budget | `partial_reason=timeout` |
| `truncated` or more candidates than `max_items` | `partial_reason=limit_reached` |
| `max_hops == 0` | seeds only, `complete=true`, `graph_status=disabled` |
| no matching seeds | empty, `complete=true`, `graph_status=no_seeds` |

Seeds are always retained when the graph fails; `RetrievalError` is raised only
when no usable items exist. `config["graph_status"]` records `ok`, `disabled`,
`no_seeds`, `unavailable`, `revision_mismatch`, or `provider_error`, plus
`graph_error` when applicable.

## Not claimed

This module does **not** assert that graph-guided retrieval improves
localization or repair success — that requires evaluation runs (Workstream B/Q-B7
`ground_truth`). Live FalkorDB expansion remains unverified (A2.4 blocked).

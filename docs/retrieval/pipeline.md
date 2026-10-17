# Retrieval pipeline (A3.6)

`src/tracefix/retrieval/pipeline.py` — `RetrievalPipeline` runs several C2
`RetrievalStrategy` arms on one query and returns a single `RetrievalResult`
that still satisfies the retrieval contract. It is the end-to-end retrieval
entry point: lexical + graph-guided + optional dense, fused with RRF.

## Construction

```python
RetrievalPipeline(strategies, *, method="rrf", rrf_k=60)
```

- `strategies` must be non-empty; the configured order is significant (see dedup).
- `method` is validated against `SUPPORTED_METHODS` (`"rrf"` only — DBSF is
  deferred, D7). An unknown method raises `ValueError`.

Typical wiring (dense stays off unless enabled):

```python
dense = build_dense_strategy(DenseConfig(enabled=False), corpus)  # -> None
arms = [LexicalBM25Strategy(corpus), GraphGuidedStrategy(provider, lexical)]
if dense is not None:
    arms.append(dense)
pipeline = RetrievalPipeline(arms)
```

## Behavior

1. **Run** each arm on the same `RetrievalQuery`; an arm raising is recorded as
   an error and isolated (`config["outcomes"]`), never propagated.
2. **Revision filter** — items whose `source_revision != query.revision` are
   dropped and counted (`config["revision_mismatches"]`); a non-zero count marks
   the result degraded (`strategy_error_recovered`), since arms share one revision.
3. **Fuse** surviving rankings with RRF (`score = Σ 1/(k + rank_i)`), tie-break
   by ascending `evidence_id`.
4. **Dedup** by `evidence_id` — the first arm (configured order) supplies
   `provenance`/`source`/`target`; the fused RRF `score` and `strategy="fusion"`
   are applied; `config["duplicates_removed"]` counts merges.
5. **Cap** to `limits.max_items`; over-cap → `limit_reached`.

## Determinism

Fusion scores are insensitive to arm order; ties break by `evidence_id`; ranks
are dense and 1-based. Arm order only affects which arm supplies a shared item's
`provenance`/`source` (documented, deterministic).

## Result

- `strategy = "fusion"`; items preserve original `provenance`, `source`, and
  `source_revision`.
- `complete=true` only when every arm succeeded, no arm was incomplete, no
  revision mismatch occurred, and the fuse was not truncated.
- otherwise `complete=false` with a `partial_reason` chosen by precedence:
  `timeout` → `graph_unavailable` → `strategy_error_recovered` →
  `index_incomplete` → `limit_reached`.
- `config`: `fusion`, `rrf_k`, `strategies`, per-arm `outcomes`
  (`status`/`item_count`/`complete`/`partial_reason`/`error`),
  `revision_mismatches`, `duplicates_removed`.
- `RetrievalError` is raised only when **every** arm fails.

## Context handoff

`pipeline.explain(evidence_id)` returns the first graph path from an
arm exposing `explain()` (i.e. `GraphGuidedStrategy`). `pipeline.to_candidates(
result, content_resolver)` adapts the fused result into
`ContextCandidate`s with graph paths attached — the only coupling to the context
selector (A3.5), which consumes fused `RetrievalResult`s unchanged via
`candidates_from_result`.

## Tests

- `tests/unit/retrieval/test_dense.py` (12): config boundary, offline backend
  determinism, empty/non-match, typed errors, dimension/count validation,
  query-embed failure, cosine ranking + tie-break.
- `tests/unit/retrieval/test_pipeline.py` (16): single/multi-arm fusion, dedup,
  arm-order insensitivity, provenance-wins, empty, incomplete + reason
  precedence, failure isolation, all-fail, revision mismatch, truncation,
  config validation, C2 semantics, and end-to-end lexical+graph with graph
  unavailability and context handoff.
- `tests/unit/retrieval/test_fusion.py` (7, pre-existing) and
  `test_context_selector.py` (18, pre-existing) still cover the fused/scored and
  selection layers.

All are fixture-based / in-memory. **No live FalkorDB test** is included
(A2.4 blocked; Docker unavailable).

## Deferred

- DBSF fusion (needs an authoritative, cited definition — D7/A4.2).
- A real dense model backend and any quality comparison (model selection +
  evaluation, Workstream B / A6).

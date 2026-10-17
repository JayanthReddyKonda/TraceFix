# Dense retrieval adapter (A3.4)

`src/tracefix/retrieval/dense.py` — an **optional, feature-flagged** dense
retrieval arm implementing the C2 `RetrievalStrategy` protocol. Disabled by
default; nothing is imported, downloaded, or initialized when disabled.

## Configuration boundary

`DenseConfig` (pydantic, serializable): `enabled` (default `false`), `backend`
(`"hashing"` | `"model"` | custom), `dimension`, `model`, `seed`.

`build_dense_strategy(config, documents, *, backend=None)`:

- `enabled=false` → returns `None`; **no backend is constructed**.
- `enabled=true`, `backend="hashing"` → builds the deterministic offline
  backend (below).
- `enabled=true`, `backend="model"` with an injected `DenseBackend` → uses it.
- `enabled=true`, `backend="model"` **without** a backend → raises a typed
  `DenseBackendUnavailableError` (no model is approved/selected; that decision is
  deliberately not made here).
- unknown backend name → `DenseBackendUnavailableError`.

The `DenseBackend` protocol is `name`, `dimension`, `encode(texts) -> list[list[float]]`.
A real model backend is supplied by injecting an implementation; nothing else
changes.

## Offline backend

`HashingEmbeddingBackend` is a deterministic, dependency-free feature-hashing
embedder (stable blake2b digest → signed dimension, L2-normalized). It is
**non-semantic** — it exists so the adapter and ranking plumbing are runnable and
testable without a model. It makes no quality claim.

## Ranking and semantics

Identical to the lexical baseline so the arms are comparable and fusable:

- documents embed `CorpusDocument.text` (see `docs/retrieval/lexical.md`);
- score is cosine similarity, sorted by descending score then ascending
  `evidence_id`;
- score `<= 0` items are dropped; ranks are dense and 1-based;
- `take = min(query.k, limits.max_items)`;
- empty corpus → `index_incomplete`; over-`k` → `limit_reached`; over time →
  `timeout`; no match → complete empty;
- items are `provenance=observed`, `source="dense"`, `source_revision=query.revision`.

## Failure semantics

- Backend fails to embed the corpus at construction → `DenseBackendUnavailableError`.
- Backend returns the wrong embedding count/dimension → `DenseBackendUnavailableError`.
- Backend fails to embed the query at retrieval time → `RetrievalError` (no raw
  exception crosses the strategy boundary).

## Deferred

Real model selection, its token/D4 compatibility, and any quality claim are
deferred. `DenseConfig.estimated=true` records that dense is not a measured
quality arm.

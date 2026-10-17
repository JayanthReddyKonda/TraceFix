# Context manifest (A5)

`src/tracefix/retrieval/manifest.py` assembles a reproducible record of the
context selected for one case revision. It implements the **stable,
contract-supported subset** of `contracts/context_manifest.json`
(v0.1.0-draft) and deliberately does **not** finalize contract C3.

> Implementation facts below describe what the code does now. Anything labeled
> *open* is a Workstream B decision and is deliberately not decided here.

## Building a manifest

```python
from tracefix.retrieval.manifest import build_manifest

manifest = build_manifest(
    selection,          # ContextSelection from ContextSelector.select(...)
    retrieval,          # optional RetrievalResult (revision + strategy config)
    repo="https://github.com/psf/requests",
    case_id=None,       # optional, never invented
    run_id=None,        # optional, never invented
    created_at=None,
)
```

`revision` resolution order: explicit `revision=` argument, then
`retrieval.revision`, then the selected items' revision. An empty selection with
no revision supplied raises `ManifestError` — the builder never fabricates a
revision.

## Shape

Top level: `repo`, `revision`, `budget`, `strategy_config`, `items`, `totals`,
and the optional `run_id` / `case_id` / `created_at`.

- `budget` = `{ token_limit, tokenizer, estimated }`, copied verbatim from the
  selection's `ContextBudget`.
- `strategy_config` = `{ "retrieval": <RetrievalResult.config>, "selector":
  <ContextSelection.config> }` when a retrieval result is supplied.
- `items` = one `EvidenceItem` per selected item; field names mirror the draft
  `evidence_item`: `evidence_id`, `evidence_type`, `repo`, `revision`,
  `file_path`, `symbol`, `lines`, `strategy`, `rank`, `score`, `graph_path`,
  `expansion_explanation`, `selection_reason`, `token_contribution`,
  `provenance`, `source`.
- `totals` = `{ tokens, item_count, duplicates }`.

## Validation rules (enforced on construction)

1. `totals.item_count == len(items)`
2. `totals.tokens == sum(item.token_contribution)`
3. `totals.tokens <= budget.token_limit`
4. `evidence_id` is unique within the manifest
5. every item declares a non-empty `provenance` and `source`
6. every item carries a `revision`, and it equals the manifest `revision`

Violations raise `pydantic.ValidationError` (a `ValueError`). An empty selection
with no derivable revision raises `ManifestError`. These implement the draft's
stated rules; they are *not* a claim that C3 is finalized.

## Evidence traceability

Each item preserves the producing strategy, its `rank`/`score`, the retrieval
`source` (e.g. `bm25`, `graph_callers`) and the `provenance`
(`observed`/`inferred`). Graph-guided expansion is carried through
`graph_path` (node/edge sequence) and `expansion_explanation`
(human-readable reason), so `manifest.explain(evidence_id)` returns the path
when one was recorded. `selection_reason` records why the selector kept the
item (`top_ranked` or `diversity_spread`).

No raw content is stored: the draft `evidence_item` has no content field, and
transport / raw-content policy are unresolved (Q-B5, Q-B6).

## Token-accounting semantics

Token counts are always labeled. `budget.tokenizer` records `name`, `encoding`,
`method` and `estimated`, and `budget.estimated` mirrors it:

- `CharDiv4TokenCounter`: `method="char_div_4"`, `encoding=null`,
  `estimated=true` — a deterministic, dependency-free estimate.
- `TiktokenTokenCounter`: `method="tiktoken"`, `encoding="cl100k_base"` by
  default, `estimated=false` — exact, but only when `tiktoken` is installed.

The manifest never recomputes tokens; it records the selector's accounting so
the two stay consistent.

## Determinism

`ContextManifest.to_json()` serializes with sorted keys and omits `None`
values, so identical inputs produce identical bytes; `model_validate_json`
round-trips without loss.

## Unresolved C3 / Workstream B decisions (isolated, not answered)

- **Q-B1 budget ownership** — the `token_limit` is whatever the caller passed to
  the selector; the manifest records it, it does not choose it.
- **Q-B2 budget scope** — counts are evidence-only here; whether manifest/cert
  overhead is included is undecided.
- **Q-B3 cross-run evidence identity** — `evidence_id` is recorded as produced;
  no cross-run identity scheme is imposed.
- **Q-B4 tokenizer compatibility** — the tokenizer is copied from the selection
  (D4); the caller owns the choice.
- **Q-B5 transport** — no transport is chosen; `to_json()` returns a string.
- **Q-B6 raw content** — no content is stored; only references.
- **`run_id` / `created_at`** — optional and never synthesized; their semantics
  are undecided.

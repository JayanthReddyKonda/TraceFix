# Context selection (A3.5)

`src/tracefix/retrieval/context_selector.py` — deterministic, token-budget-aware
selection of ranked retrieval items into an evidence package with an explicit
reason for every input. It consumes C2 `RankedItem`s (e.g. from
`GraphGuidedStrategy`) and preserves `evidence_id`, `source_revision`,
`provenance`, and `source`.

## Not the manifest (C3 stays draft)

This is **not** `manifest.py` (A5.2) and does not finalize
`contracts/context_manifest.json`. It supplies the per-item material the draft
`evidence_item` needs (field names match) plus budget/totals accounting, and
deliberately leaves open Workstream B questions unanswered:

- the budget is **supplied by the caller** (`token_limit`) and only recorded
  (Q-B1);
- budget scope is evidence-only here; whether repair scaffolding counts is left
  open (Q-B2);
- raw content is provided by the caller; no transport or raw-content policy is
  chosen (Q-B5, Q-B6);
- manifest-level fields (`run_id`, `created_at`) are absent — A5's job.

`repo` and `evidence_type` are optional passthroughs (filled by manifest
assembly, not invented here).

## Tokenizer (configurable; exact vs estimated)

Every counter exposes `count(text) -> int` and `config()` matching
`token_accounting.config` (`name`, `encoding`, `method`, `estimated`):

| Counter | method | estimated | Notes |
|---|---|---|---|
| `CharDiv4TokenCounter` | `char_div_4` | `true` | Dependency-free estimator, `ceil(len/4)`. Default. |
| `TiktokenTokenCounter` | `tiktoken` | `false` | Exact; requires the `tiktoken` extra; records its encoding. |

The chosen counter's `config()` and `estimated` are copied verbatim into
`ContextSelection.budget`, so a consumer can always tell measured from
estimated figures (no bare unlabeled token numbers).

## Candidates

`ContextCandidate` = a `RankedItem` plus the `content` text to count, and
optional `graph_path` (node-id sequence from A3.3 `explain()`),
`expansion_explanation`, `evidence_type`, `repo`. `from_item(...)` builds one.

## Selection algorithm (deterministic)

1. **Order** candidates by `(rank, evidence_id)` — stable, input-order
   independent.
2. **Dedup** by `evidence_id` (first occurrence wins); each dropped duplicate is
   recorded with reason `duplicate` and counted in `totals.duplicates`.
3. **Greedy single pass** in that order:
   - cost `> token_limit` → excluded `item_too_large` (can never fit).
   - over a diversity cap → excluded `diversity_cap`.
   - cost `> remaining budget` → excluded `over_budget`, and the scan
     **continues** so later, smaller items still pack the budget.
   - otherwise kept; reason is `diversity_spread` if it introduces a
     not-yet-represented file, else `top_ranked`.

Diversity caps (`max_items_per_file`, `max_items_per_source`) are **hard**, so
the budget may be left under-filled when a cap binds. `totals.tokens <=
token_limit` and `totals.tokens == sum(item.token_contribution)` and
`totals.item_count == len(items)` are enforced by the model.

## Output

`ContextSelection`: `items` (`SelectedItem`), `excluded` (`ExcludedItem` with
`reason`), `budget` (`token_limit`, `tokenizer`, `estimated`), `totals`
(`tokens`, `item_count`, `duplicates`), and `config` (selector caps + ordering).

## Tests

`tests/unit/retrieval/test_context_selector.py` (18): empty inputs, exact fit,
one-token-short boundary, over-budget skip-and-pack, item-too-large, duplicates,
zero-length content, file/source diversity caps, spread vs top-ranked reasons,
input-order determinism, exact-vs-estimated counters, metadata preservation,
input validation, model bound checks, and an end-to-end run through
`GraphGuidedStrategy` carrying `graph_path`.

## Not claimed

Selection quality is not an evaluation result: no claim that a given budget or
capping scheme improves localization or repair. Live FalkorDB expansion remains
unverified (A2.4 blocked).

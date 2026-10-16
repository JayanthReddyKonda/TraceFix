# Lexical retrieval baseline (A3.2)

`src/tracefix/retrieval/lexical.py` — deterministic BM25 baseline over
function-level documents. This is the comparison arm for graph-guided
retrieval; it must stay reproducible so differences are attributable to the
graph, not to tokenizer or tie-break drift.

## Documents

One document per `Function`/`Test` node from an ingestion snapshot. Document
text is the concatenation of:

1. the qualified name (`calc.core.accumulate`),
2. the repo-relative path,
3. the signature property,
4. the source segment `[start_line, end_line]` read from the checkout.

Segments are read from disk, so the corpus matches the snapshot's revision only
when the checkout is at that revision.

## Tokenizer

Documented, fixed scheme (`_tokenize`): lowercase, then
`re.findall(r"[a-z0-9]+", ...)`. This splits on every non-alphanumeric character
**including underscores**, and does **not** split camelCase. `test_add` →
`["test", "add"]`; `parseURL` → `["parseurl"]`. The scheme is recorded in
`LexicalBM25Strategy.config["tokenizer"]` on every result.

## Scoring and determinism

- `rank_bm25.BM25Okapi` with `k1=1.5`, `b=0.75` (both in `config`).
- Candidates are sorted by descending score, then by **ascending
  `evidence_id`**, so equal scores always break identically.
- Items with score `<= 0` are dropped; ranks are dense and 1-based.
- `take = min(query.k, limits.max_items)`.

## Result semantics (C2)

- Empty corpus → `complete=false`, `partial_reason=index_incomplete`.
- More matching documents than returned items → `limit_reached`.
- Wall-clock over `limits.timeout_ms` → `timeout` (checked after scoring).
- No matching documents → empty, `complete=true`.
- `source_revision` on each item is the query revision; every item is
  `provenance=observed` with `source="bm25"`.

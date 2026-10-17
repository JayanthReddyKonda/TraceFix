# A6b Experimental Protocol (Controlled Study)

> **Status:** PROPOSED — protocol for review, not an execution approval. Do not launch comparative experiments until prerequisites confirmed. This is a controlled study; no retrieval/repair improvement claims.

## 1. Purpose

Compare three retrieval arms on the frozen Requests case set using the existing single-arm evaluation infrastructure (injected strategy). Dense disabled by default. No DBSF.

Arms:
- **Arm A (lexical):** BM25 over code identifiers/text (baseline). Implementation: `retrieval/lexical.py`.
- **Arm B (graph-guided):** graph-guided expansion + ranking via typed graph queries (uses existing `retrieval/graph_guided.py`, `graph/query.py`).
- **Arm C (fused):** RRF fusion of lexical + graph-guided (`retrieval/fusion.py`, `fuse_ids` with RRF). 

## 2. Case set & ground truth

- Frozen set: `eval/cases/requests_swe_bench_candidates.json` (read-only). 
- Fingerprint: `da1c89d31006ac65753d31fcb719b457ce5cb000e14e0735126018a90e350858` (localizable pairs + `evaluation_contract_version`).
- Counts: total 44, localizable 43, excluded 1 (`psf__requests-4106`, reason `no-enclosing-function-derived-from-gold-hunk`), all pre-cutoff (100%).
- GT: provisional (Q-B7). GT functions are enclosing functions of added gold-patch lines (heuristic). Vendored paths under `requests.packages.*` present; treat as potential over-attribution (see C4/D8). 
- `fix_commit`: null for all (not present in captured SWE-bench rows). 
- Do not fabricate fix commits or mutate GT.

## 3. Repository state

- Repo: `psf/requests` at recorded `revision` per case (buggy snapshot). Use exact SHA from case record.
- Index/state: use the repo copy if needed (`data/repos/requests` exists, gitignored) or work from source; do not rewrite history. No cross-case revision leakage.
- Determinism: strategies must be deterministic given same inputs/revision (no hidden nondeterminism). 

## 4. Evaluation target (retrieval vs context)

- **Primary:** evaluate **raw retrieval rankings** from each strategy (before final budget selection) against GT functions, using the same k and same eligible set. Rationale: avoids conflating selector policy with retrieval quality. 
- **Secondary (diagnostic):** evaluate the **budgeted context** produced by `ContextSelector`/manifest against GT (same budget across arms if comparable). Report both with config.
- Evidence is function/file-level items per C2; manifest is deterministic (A5).

## 5. Fairness controls

- Same case set, same revisions, same fingerprint. Run each arm with identical case order (or just same set). 
- Comparable **evidence budget**: if comparing final context, use same `token_limit` and same tokenizer accounting; document any difference and justify. 
- No extra evidence sources for graph-guided (only existing typed graph). 
- Lexical and graph-guided are independent; fusion uses only their outputs (RRF). 
- Strategy config serialized and recorded in run record (`strategy_name`, `strategy_config`). 
- Failures/timeouts: record per case (`status`, `error`, `partial`, `note`). Never score failures as 0 for metrics; count them separately. 
- Nondeterministic latency: record per-case elapsed_ms and report aggregates (mean/median/p95 if enough samples) but treat latency as diagnostic unless specified. 
- No live FalkorDB required for protocol; if graph unavailable in a run, strategy must fail gracefully and record it (service-free tests show patterns). 
- Dense must remain **disabled** unless a separate, documented justification exists (no authoritative DBSF). 

## 6. Metrics & denominators

Primary/secondary per Q-B8/Q-B9/Q-B11 (proposed):

- **Hit@k (primary): any-hit.** 1 if any GT function appears at rank <= k. Denom: localizable cases with non-empty `ground_truth_functions` (n=43). 
- **Recall@k:** report **micro-recall@k** (total GT functions retrieved in top-k / total GT functions across evaluated cases) and **macro-recall@k** (mean per case). Undefined only when denom case has no GT? GT is non-empty for localizable cases here (and excluded only when unlocalizable). 
- **First relevant rank (diagnostic):** rank of earliest GT function; censored if absent (record as undefined, not 0).
- **File-level (secondary):** Hit@k/file, micro/macro recall@k at file granularity (if any GT file appears). 
- **All-hit@k (sensitivity):** all GT functions by k — report separately.
- **Context metrics (if comparing context):** tokens (manifest totals), selected count, duplicates, source coverage — as implemented.
- **Latency (diagnostic):** per-case ms; mean + undefined count. 
- **Failures/exclusions/partials:** reported separately. 
- k in {5,10,20}, **primary k=10**.

**Rules:** every rate must include numerator and denominator. Undefined rates never reported as 0. Excluded cases never enter denominators. `cases_failed`, `cases_partial`, etc tracked.

## 7. Run protocol (stepwise)

1. **Load case set** (read-only): verify fingerprint matches; record `case_set_fingerprint`, `fingerprint_includes_excluded=False`. 
2. **Arm A (lexical):** construct query from bug report (and minimal context); run on all localizable cases; write single-arm run record via `EvaluationRunner`/`evaluate_case_set` (inject strategy). Record `strategy_name="lexical"`, full config.
3. **Arm B (graph-guided):** same set/query policy; record `strategy_name="graph_guided"`. 
4. **Arm C (fused):** fusion of A+B outputs (RRF) with same inputs; record `strategy_name="fusion_lexical_graph_rrf"`. 
5. **Reproducibility:** generate reproducible JSON (include_volatile=False) for each arm; compare stable fields. Volatile (generated_at, env) excluded. 
6. **Aggregate & disclose:** contamination (44/44 pre-cutoff), provenance (`provenance_verified=False`, raw rows path/checksum), provisional GT, undefined counts, denominators.

## 8. Data capture

Per run record must include (from current schema): case_set_fingerprint, evaluation_contract_version, strategy_name/config, metric_config, command, dataset (ground_truth_is_provisional, provenance_verified, source, license), contamination, denominators, excluded, aggregate, cases[]. Also environment excluded from stable; generated_at volatile. 

Add provenance block to experiment report:
- dataset_source: swe-bench (captured subset)
- raw_rows_path: `eval/cases/source/swebench_requests_rows.json`
- raw_rows_sha256: `ab348fe92029fa3b5a2d52b1fa2e71916bb43ead7a84deb067cb2495f74ac589`
- upstream_url/tag: **unknown** (not recorded)
- license: Apache-2.0
- fix_commit_status: missing (not present in captured rows)
- gt_heuristic: enclosing_added_lines (enclosing functions of added gold-patch hunks)
- gt_status: provisional (Q-B7)

## 9. Contamination & limitations

- 100% pre-cutoff (created_at <= 2022-01-04). 
- Small sample (n=43). No benchmark claims. 
- GT provisional; vendored `requests.packages.*` may over-attribute. 
- Raw-row provenance incomplete (no upstream tag/URL, no fix_commit). 
- Test-patch presence ≠ tests passing (no execution harness). 
- Live FalkorDB/Docker not assumed. 

## 10. Prerequisites check

**Ready:** A6a runner (injectable), metrics with denominators/undefined, frozen set immutable + fingerprint, manifest deterministic, pipeline+strategies exist, contract markers/tests green.  
**Needs confirmation (B):** adopt Q-B7–Q-B12 proposed defaults (esp. vendored policy, micro-recall required, primary k=10, any-hit primary).  
**Blockers if violated:** changing fingerprint/frozen set, fabricating fix commits, claiming provenance verification, or running without recording strategy_config+revisions+denominators. 

## 11. Deliverables for review

1. This protocol (`docs/experiments/a6b_protocol.md`).  
2. C4/D8 decisions (`docs/experiments/c4_d8_decisions.md`).  
3. Ledger update noting proposed vs ready vs blocked.  
4. Focused tests only if audit finds concrete gaps (none identified so far). 

**Stop condition:** after delivering these; do not execute comparative runs. 

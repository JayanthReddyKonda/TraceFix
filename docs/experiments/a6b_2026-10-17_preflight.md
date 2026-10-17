# A6b Preflight & Feasibility (2026-10-17)

**Status:** Preflight PASSED for case set; comparative runs **NOT EXECUTED** (infeasible in this environment). Controlled study only; no improvement claims.

## 1. Preflight (Stage 1)

| Check | Result | Evidence |
|---|---|---|
| Case-set fingerprint matches frozen set | OK | `da1c89d31006ac65753d31fcb719b457ce5cb000e14e0735126018a90e350858`; loader verifies |
| Counts/exclusions/revisions | OK | total 44, localizable 43, excluded 1 (`psf__requests-4106`), all pre-cutoff (100%) |
| Provisional GT status recorded | OK | `ground_truth_status="provisional (pending Q-B7)"` |
| Raw dataset checksum | OK | `eval/cases/source/swebench_requests_rows.json` sha256 `ab348fe92029fa3b5a2d52b1fa2e71916bb43ead7a84deb067cb2495f74ac589` |
| Upstream provenance limitations documented | OK | No upstream URL/tag recorded; `fix_commit` null for all; provenance_verified=False (documented in protocol/C4-D8) |
| Runner records partials/errors/exclusions | OK | `EvaluationRunner`/`evaluate_case_set` track cases_failed/partial, denominators explicit, undefined never zero |
| Live FalkorDB available | NO | Docker not running; `falkordb` not installed. Graph-guided cannot run against live graph. |
| Strategies exist and injectable | OK | `lexical.LexicalBM25Strategy`, `graph_guided.GraphGuidedStrategy`, `fusion.fuse_ids`/pipeline patterns present; single-arm runner injectable |

Repository: `psf/requests` case set (frozen, read-only). Git HEAD: `3e37aa9ba3568df8f7f1df66e2fc485cdf102f17` (branch `suhaas`), pushed to origin/main and origin/suhaas. All gates green (224 passed, ruff clean, mypy clean, 18 contract).

## 2. Feasibility

- **Arm B (graph-guided):** requires `NeighborhoodProvider` over a graph at the case revision (typed queries). Without a live FalkorDB instance and populated graph snapshots per revision, real neighborhoods cannot be obtained. Substituting stubs would violate "do not silently substitute mock graph results and describe them as real graph retrieval".
- **Arm C (fused):** depends on real outputs from A and B (RRF). Without real B (and corpus for A), fusion cannot be computed on real retrieval rankings.
- **Arm A (lexical):** `LexicalBM25Strategy` expects a prebuilt function-level corpus (from ingested nodes + repo source). We do not have ingested graph artifacts/snapshots for all revisions; building full corpus for 43 localizable cases across their specific SHAs is nontrivial in this environment without ingestion pipeline runs.

Conclusion: **Full A/B/C comparative run with real retrieval components is infeasible without FalkorDB and ingestion snapshots.**

## 3. Proposed subset protocol (explicit, not cherry-picked by outcome)

If a minimal diagnostic is desired later (with approval), run **only** on a small, pre-declared subset selected **before** any runs by fixed criteria:

- Criteria (fixed, outcome-independent): cases with `localizable=True`, `revision` accessible, single-function GT (len==1) to minimize ambiguity, and not in `requests.packages.*` heavy cases. 
- Subset size: e.g. 5 cases (or up to 10), explicitly listed and justified. 
- For subset only: if running graph-guided, must use real graph (FalkorDB available). If not available, do **not** run B/C as real arms — report "unverified". 
- For subset only: lexical can run if corpus built from nodes at those revisions; otherwise skip. 
- Report full denominators (43 eligible total) and that subset is diagnostic only, not representative.

Do **not** select based on preliminary Hit@k or to "improve" results.

## 4. What was executed

- Case set validation, fingerprint verification, raw sha256 computation: executed (read-only). 
- No retrieval runs executed for A/B/C. No experiment results written beyond this document.

## 5. Limitations (as stated in protocol)

- GT provisional (Q-B7); vendored paths may over-attribute. 
- `fix_commit` missing for all (not in captured rows); upstream URL/tag unknown. 
- 100% pre-cutoff contamination. Small sample (n=43). 
- No benchmark/generalization claims.

## 6. Next step

Await review/confirmation of feasibility and subset protocol (or provision FalkorDB + ingestion artifacts). Do **not** launch comparative experiments until real components available or subset approved. 

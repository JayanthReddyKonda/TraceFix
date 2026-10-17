# C4/D8 Decision Proposal (A6b readiness)

> Status: **PROPOSED**, not approved. Workstream B must confirm. Defaults below are defensible for a small controlled study; they do not finalize C4.

## Summary

- Ground truth is **provisional** (pending Q-B7). No modification to the frozen set.
- Propose: function-level primary (Q-B9), k in {5,10,20} with **primary k=10** (Q-B8), any-hit for Hit@k (Q-B11) with micro-recall as a required sensitivity, fingerprint as recorded (Q-B10), controlled-study disclosure (Q-B12/D8).
- Key gaps: `fix_commit` missing for all 44 (not available in the captured SWE-bench rows), raw-row provenance not fully verifiable from the committed artifacts, and over-broad GT (vendored `requests.packages.*`, some class/module-heavy cases).

## Q-B7 — Ground-truth derivation

### Observations
- Current GT derived from "enclosing function(s) of added gold-patch lines" (script + docs). `eval/cases/requests_swe_bench_candidates.json` has 43 localizable, 1 excluded (`psf__requests-4106`: `no-enclosing-function-derived-from-gold-hunk`).
- Examples: `psf__requests-1142` → 1 function (`requests.models.PreparedRequest.prepare_content_length`). `psf__requests-2678` → 53 functions, many under `requests.packages.urllib3.*` (vendored). `psf__requests-1339` → 12 functions (broad).
- Gold patches exist (SWE-bench rows) and base commits match (verified offline). `fix_commit` is **null for all 44** in the frozen set (raw rows lack it; not derivable from captured rows).
- No test labels were fabricated.

### Issues
- **Vendored attribution:** Including `requests.packages.*` (urllib3/pyopenssl/appengine) as "ground truth functions to localize" conflates local changes in the vendored copy vs upstream; may dilute or misattribute.
- **Class/module-level changes:** Some patches touch multiple classes/modules; enclosing-function heuristic may miss or over-include.
- **Multi-line moves/renames:** Qualified names may not uniquely identify targets; heuristic is heuristic.
- **Test patches:** Present in rows (`test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`) but "test passes" not verified in this environment (Docker/downstream test harness absent).

### Recommendation (PROPOSED)
- Keep current frozen set as-is (read-only). **Do not** retroactively fill `fix_commit` without citing a concrete upstream source (SWE-bench release tag/revision) and checksum.
- **Normalization policy (proposed, apply to future GT derivation only; do not mutate existing set):** 
  - Prefer function-level qualified names when hunk lines map to function defs; fall back to class if only class scope; else file-level if pure config/data (and treat as unlocalizable by current rule or file-level).
  - **Exclude or flag vendored paths** under `requests/packages/*` (and submodules) unless the case is explicitly about vendored code and justified. For `psf/requests`, vendored urllib3 is often upstream; report a separate "vendored" slice.
  - Record GT provenance fields: `gt_heuristic = "enclosing_added_lines"`, `gt_version = "<sha256 of raw rows used>"`, `gt_normalized = false` for the frozen set.
- **Status:** Provisional (Q-B7). Require independent spot-check of >= 10 cases (5 single-function, 5 multi) before upgrading to "validated".

## Q-B8 — Primary k

### Recommendation (PROPOSED)
- **k values:** {5, 10, 20} (matches common SWE-bench retrieval practice; sensitivity space small).
- **Primary k:** **10**. Rationale: balances small context budgets and realistic developer inspection; Hit@10 is stable for small samples while avoiding saturating Hit@20 for very local single-hunk fixes. Secondary: Hit@5 (strict), Hit@20 (lenient). Document all three.

## Q-B9 — File-level vs function-level

### Recommendation (PROPOSED)
- **Primary:** function-level localization (what the code/selector+manifest currently track). Matches "ground_truth_functions".
- **Secondary (diagnostic):** file-level Hit@k/Recall@k (treat file hit if any GT function’s file appears; use same denominators policy). Report both; do not let file-level supplant function-level. Keep manifest items traceable to file+symbol.

## Q-B10 — Fingerprinting

### Current
- `case_set_fingerprint = sha256(json.dumps(sorted((c.case_id,c.revision) for c in localizable), separators=(",",":")) + ["evaluation_contract_version"] payload?)` — loader computes: `payload = json.dumps([pairs, contract_version], separators=(",", ":"))` and stores `case_set_fingerprint` in the frozen set (matches `da1c89d31006ac65753d31fcb719b457ce5cb000e14e0735126018a90e350858`).
- Contract states: "sha256 over the sorted list of (case_id, revision) pairs plus the evaluation contract version". Also states "fingerprint matches recorded" and excludes excluded cases (localizable only). Runner reports `fingerprint_includes_excluded = False`.

### Recommendation (PROPOSED)
- **Keep current method** (backward compatible). Do not change existing fingerprint. If policy evolves, bump `evaluation_contract_version` and compute new fingerprint; record both in report (`case_set_fingerprint`, `case_set_fingerprint_source`, `fingerprint_includes_excluded`).
- **Mandate:** fingerprint includes only **localizable** cases (by id+revision) + `evaluation_contract_version`. Excluded cases must never enter fingerprint. Any metadata change (ground_truth_status text) must not affect fingerprint. 
- **Implication:** If we later normalize GT (Q-B7) without changing which cases are localizable or their (id,revision), fingerprint **must remain the same**. If we exclude additional cases, fingerprint changes — must document and gate.

## Q-B11 — Multi-function fixes

### Observations
- Current metrics: `hit_at_k` is any-hit (returns 1 if any GT function in set by rank<=k). `recall_at_k` is fraction of GT functions present by rank<=k (macro/mean over cases as implemented? metrics.py: `recall_at_k` returns average over cases that have any GT; micro-recall also provided). Also `first_relevant_rank` exists.
- Some cases have many GT functions (2678 has 53). 

### Recommendation (PROPOSED)
- **Hit@k (primary): any-hit** — retrieval success = surfaced at least one relevant function in top-k (pragmatic for "find something to fix"). 
- **Required sensitivity:** **micro-recall@k** = (total relevant functions retrieved in top-k across cases) / (total relevant functions across evaluated cases), reported with numerator/denominator. Also report **macro-recall@k** (mean per case). 
- **Additional (diagnostic):** **all-hit@k** = 1 only if all GT functions retrieved by k (separately reported, never replaces primary Hit@k unless B approves). 
- **Aggregation:** only over evaluated localizable cases with non-empty GT; undefined cases never become 0. Report `undefined_recall_count` etc as implemented.

## Q-B12/D8 — Dataset and contamination

### Current set
- Source: `swe-bench`-derived rows (captured), repo `psf/requests`, 44 instances total → 43 localizable, 1 excluded. All pre-cutoff (`created_at` max 2022-01-04 < 2024-01-01). 
- Fingerprint recorded. License Apache-2.0 (stated). 
- Raw rows: `eval/cases/source/swebench_requests_rows.json` (44). Checksum (sha256 over canonical JSON, list of dicts): `ab348fe92029fa3b` (first 16 hex) as computed above. 
- Upstream URL/revision tag: **not recorded** in frozen set or committed artifacts beyond "swe-bench" label. `fix_commit` **null for all** (cannot be reconstructed from captured rows alone).

### Gaps
- No explicit upstream dataset **version/release tag** (e.g., SWE-bench vX.Y). 
- No URL to the exact upstream snapshot. 
- `fix_commit` absent (committed rows don’t include it in this capture). 
- Provenance: "UNVERIFIED" in practice; runner surfaces `provenance_verified = False`.

### Recommendation (PROPOSED)
- **Treat as controlled study only.** Do not claim "SWE-bench subset validated".
- **Disclose explicitly:** contamination = 44/44 pre-cutoff (100%). Results may not generalize to post-cutoff bugs. 
- **Provenance action (read-only):** Add to `docs/experiments/a6b_protocol.md` a provenance block with: dataset_source, repo, counts, localizable/excluded, cutoff, created_at range, raw_rows_path, raw_rows_sha256 (`ab348fe92029fa3b...` full hex to be recorded), upstream URL/tag if discoverable (or "unknown"), license, fix_commit_status="missing (not present in captured rows)", ground_truth_status="provisional (Q-B7)". 
- **Adequacy:** 43 localizable is small but sufficient for a **single-arm diagnostic** and for a careful **A/B/C comparison** with fairness controls and explicit denominators. It is **not** adequate to make strong general claims or to power fine-grained ablations; report precision of estimates and avoid p-hacking. 
- **Terms:** State Apache-2.0 license; respect SWE-bench terms if using upstream data.

## Test/patch usability note

- `FAIL_TO_PASS`/`PASS_TO_PASS` and `test_patch` exist. "Test actually passes" requires execution environment (harness). Docker not running; no integration runs. Do not claim test-based validation. Record this limitation.

## Prerequisites (for starting comparative A6b)

**Ready (verified):** single-arm runner injectable, metrics with denominators/undefined handling, frozen set read-only + fingerprint, manifest + selector, pipeline (lexical+graph-guided+fusion RRF).  
**Proposed (need B confirmation or explicit proceed-with-proposal):** Q-B7–Q-B12 defaults above.  
**Blocked/uncertain:** upstream provenance completeness, vendored GT policy adoption (impacts denominators interpretation), fix_commit absence (irreconcilable from captured rows without upstream fetch).

## Compatibility

- Keep existing fingerprint (`da1c89d3…`). No change to frozen set. Contract remains `0.1.0-draft`.
- Any future GT normalization must not affect fingerprint or localizable set unless versioned and documented.

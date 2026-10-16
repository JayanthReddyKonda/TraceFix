# Workstream A — Task Ledger

Graph/retrieval workstream plan. Maintained per brief §11: updated at the start and
end of every session; a task is `DONE` only when its acceptance criteria are met and
evidence is recorded.

- Owner: Workstream A (graph + retrieval + context)
- Primary branch: `suhaas` — integration target: `main`
- Latest checkpoint decision: **Checkpoint 0 decisions recorded 2026-10-16** (see decision record below); checkpoint remains open pending D3 repo selection and D8/B contract coordination
- Session rule: pick the highest-priority `NOT STARTED` task whose dependencies are all `DONE`.

Statuses used: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `READY FOR REVIEW`, `DONE`.

---

## Checkpoint 0 decision record (2026-10-16, integration owner)

- **D1** — Approve C1–C4 in principle, with amendments and cross-workstream review.
  - C1: start with Code + History layers; stable canonical entity IDs; revision/content hashes retained separately; inferred relationships marked explicitly.
  - C2: common retrieval interface with explicit provenance, source revision, and failure/partial-result semantics.
  - C3: coordinate manifest fields and token-budget semantics with Workstream B **before implementation**.
  - C4: coordinate case schema, ground-truth policy, exclusions, and metric denominators with Workstream B **before finalization**.
- **D2** — APPROVED: use `src/tracefix/`.
- **D3** — Propose 2–3 Python repos with reproducible historical bugs, tests, accessible git history; **no real-repository ingestion until one is selected**.
- **D4** — APPROVED WITH CONDITION: configurable tokenizer interface; tiktoken only if compatible with the selected model; record encoding and estimate status.
- **D5** — APPROVED, provided the spec PDF may be redistributed in the repository.
- **D6** — APPROVED: project `.venv` + pytest/Ruff/mypy; keep service-free tests separate from FalkorDB integration tests; **no real-integration claims while Docker is unavailable**.
- **D7** — APPROVED: RRF first; DBSF deferred until its authoritative definition is cited and verified.
- **D8** — PENDING: propose initial evaluation dataset and metric rules **with Workstream B**.

---

## Phase 0 — Audit and structure plan

| ID | Task | Description / rationale | Dependencies | Acceptance criteria | Owner | Status | Tests & evidence | Files changed | Follow-up |
|---|---|---|---|---|---|---|---|---|---|
| A0.1 | Repository audit | Inspect tree, git state, entry points, deps, tests, contracts, FalkorDB setup, fixtures | none | Audit covers all 8 brief §5 items with commands and observed outputs | WSA | DONE | Command outputs in audit §1.1–1.3 | `docs/workstreams/graph-retrieval-audit.md` | Re-audit if another workstream lands code |
| A0.2 | Spec extraction | Extract the proposed report PDF into reviewable text | none | Spec facts labeled `[spec]` | WSA | DONE | 16-page PDF extracted; audit §1.4 | audit §1.4 | — |
| A0.3 | Target structure proposal | Propose module tree; reconcile brief layout vs spec §13 | A0.1, A0.2 | Structure, mapping, deferral rationale documented | WSA | DONE | audit §3 | audit §3 | Executed per D2 |
| A0.4 | Dependency & risk analysis | Propose deps from observed toolchain; risks with mitigations | A0.1 | Every dep justified; every risk has mitigation | WSA | DONE | audit §4, §5 (R1–R11) | audit §4, §5 | R1 (Docker down) still open |
| A0.5 | Contract proposals C1–C4 | Propose contracts; revise per D1 amendments | A0.1, A0.2, D1 | Files written; amendments and B-open-questions recorded | WSA | DONE | Locked by `tests/contract/` (9 tests) | `contracts/*.json`, audit §6 | Finalization of C3/C4 with B |
| A0.6 | Phase-by-phase plan + task ledger | Sequence phases with acceptance evidence and checkpoints | A0.3–A0.5 | Plan table + ledger exist | WSA | DONE | audit §7–§10; this ledger | audit §7–§10, this file | Update after every checkpoint |
| A0.7 | Branch/merge setup | Primary `suhaas`, integration on `main` | none | Work confined to `suhaas`; merged to `main` | WSA | DONE | `git branch -vv` shows both in sync with origin | n/a (git state) | — |
| A0.8 | Project tooling setup | `.venv`, `pyproject.toml`, `.gitignore`, pytest markers, ruff/mypy config | D2, D6 | Tooling installed in project venv; default test run excludes integration | WSA | DONE | `.venv/bin/pytest -q` → **15 passed** (exit 0); `.venv/bin/ruff check .` → **All checks passed**; `.venv/bin/mypy` → **Success: no issues found in 1 source file** | `pyproject.toml`, `.gitignore`, `src/tracefix/__init__.py` | Add runtime deps only via approved decision |
| A0.9 | Contract files + integrity tests | Write C1–C4 as machine-readable contracts; lock checkpoint states with service-free tests | A0.5, D1 | Contracts parse; statuses locked; D1 amendments (identity, provenance, failure semantics, B-question queues) asserted | WSA | DONE | 15 contract tests pass (part of the 15 above); first ruff run flagged 5×E501 in `test_graph_schema_contract.py` — refactored, re-run clean | `contracts/*.json`, `tests/contract/*.py` | — |
| A0.10 | Cross-workstream review of C3/C4 + D8 metric rules with Workstream B | Resolve Q-B1–Q-B12 before manifest/evaluation implementation | A0.9 | B answers recorded; C3/C4 status moves off draft via contract change | WSA | BLOCKED | Q-B1–Q-B12 queued in `contracts/context_manifest.json` and `contracts/evaluation.json`; B not present in repo yet | — | Requires B/integration owner session |
| A0.11 | Target repository selection (D3) | Choose from proposed candidates; then real-repo ingestion may begin | A0.6 | One repo named and cloned; rationale recorded | WSA | BLOCKED | Candidates proposed in audit §10 (`psf/requests` recommended) | — | Awaiting integration-owner selection |
| A0.12 | Commit spec PDF (D5) | Store spec in-repo for traceability | D5 | PDF committed at agreed path | WSA | DONE | File present, 437,824 bytes | `docs/project/tracefix-proposed-project-report.pdf` | Remove if third-party material identified |

---

## Phase 1 — Graph schema and repository ingestion  *(blocked on D3 for real-repo input; A1.1 additionally awaits C1 finalization after B review)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A1.1 | Instance-level contract tests for `contracts/graph_schema.json` | D1 (C1 finalized post-B review) | Valid sample subgraph validates; invalid subgraph rejected | NOT STARTED | — | — |
| A1.2 | `graph/models.py` + `graph/schema.py` | A1.1 | Typed entities/relations with provenance (`observed`/`inferred`) and revision fields | NOT STARTED | — | — |
| A1.3 | `graph/client.py` (FalkorDB connection, timeout, error mapping) | D6 | Connection failures/timeouts raise typed errors; no free Cypher escapes this layer | NOT STARTED | — | — |
| A1.4 | Python AST ingestion (files, modules, classes, functions, imports, calls) | A1.2, A0.11 | Parse fixtures pass; malformed input tolerated and reported | NOT STARTED | — | — |
| A1.5 | Git history ingestion (commits, authors, file changes) | A1.2, A0.11 | Missing/shallow history yields explicit `history_available: false` | NOT STARTED | — | — |
| A1.6 | Test detection + `COVERED_BY` heuristic | A1.4 | Heuristic documented as `inferred` with stated confidence | NOT STARTED | — | — |
| A1.7 | Idempotent ingestion + revision stamping | A1.4, A1.5 | Re-ingest same revision → no duplicates; different revision → new snapshot | NOT STARTED | — | — |
| A1.8 | Parser limitations doc | A1.4–A1.6 | `docs/graph/` lists unsupported constructs and confidence per relation | NOT STARTED | — | — |

## Phase 2 — Bounded graph query layer  *(blocked on A1.x + FalkorDB availability; D6: no real-integration claims while Docker is down)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A2.1 | Typed query ops: symbol lookup, file defs/imports, bounded neighborhood, covering tests, commit/incident relations | A1.3 | Each op parameterized, depth/count/time-limited, returns structured results with revision | NOT STARTED | — | — |
| A2.2 | Input validation + result normalization | A2.1 | Invalid inputs rejected; empty results distinct from errors | NOT STARTED | — | — |
| A2.3 | Failure-path tests (timeout, db down, partial result) | A2.1 | Failures explicit, no silent partial data | NOT STARTED | — | — |
| A2.4 | FalkorDB integration tests (marker-gated) | A2.1, D6 | Pinned version verified; integration suite runs via documented command | NOT STARTED | — | — |

## Phase 3 — Retrieval baselines and graph-guided retrieval  *(blocked on A2.1)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A3.1 | `retrieval/interfaces.py` (strategy protocol, `RankedItem`) | D1 (C2) | Two strategies implement the same protocol; contract test passes | NOT STARTED | — | — |
| A3.2 | Lexical baseline (BM25, documented ranking) | A3.1 | Deterministic on fixtures; tie-breaking documented | NOT STARTED | — | — |
| A3.3 | Graph-guided expansion (bounded hops, type-filtered) | A3.1, A2.1 | Hop/size limits enforced; expansion steps recorded per item | NOT STARTED | — | — |
| A3.4 | Dense adapter (feature-flagged, off by default) | A3.1, D4, D6 | Skipped without model; never downloads in default test run | NOT STARTED | — | — |
| A3.5 | `context_selector.py` (token budget, source diversity) | A3.1–A3.3 | Budget never exceeded; selection reason per item | NOT STARTED | — | — |

## Phase 4 — Score fusion  *(blocked on A3.1; D7: RRF first)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A4.1 | RRF with deterministic golden tests | A3.1 | Known ranks → expected scores | NOT STARTED | — | — |
| A4.2 | DBSF **only** with cited authoritative definition recorded in-repo | D7 | Source cited before code; name not used for a substitute formula | NOT STARTED | — | — |
| A4.3 | Fusion method selectable in config | A4.1 | Config switch changes results; both arms measurable | NOT STARTED | — | — |

## Phase 5 — Context manifest and provenance  *(blocked on A3, A4, and C3 finalization with B)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A5.1 | Contract tests for `contracts/context_manifest.json` | D1 (C3 finalized) | Valid manifest accepted; missing provenance rejected | NOT STARTED | — | — |
| A5.2 | `retrieval/manifest.py` (stable evidence ids, token estimates, serialization) | A5.1, A3.5 | Round-trip serializes; token counts labeled estimate + tokenizer | NOT STARTED | — | — |
| A5.3 | Budget accounting + duplicate/source-coverage stats | A5.2 | Totals match itemized costs; duplicates counted, not silently dropped | NOT STARTED | — | — |

## Phase 6 — Retrieval evaluation  *(blocked on A5, C4 finalization, and D8 dataset decision)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A6.1 | Case-set loader validating `contracts/evaluation.json` | D1 (C4 finalized), D8 | Invalid/unlocalizable cases handled per declared rules | NOT STARTED | — | — |
| A6.2 | Metrics: Hit@k, Recall@k, rank of fixed function, tokens, latency, counts, duplicates | A6.1 | Denominators declared; no metric without a reproducible run | NOT STARTED | — | — |
| A6.3 | Baseline-vs-graph-guided comparison runner | A3.x, A6.2 | One command runs both arms on same case set, writes config+revision metadata | NOT STARTED | — | — |
| A6.4 | First recorded experiment in `docs/experiments/` | A6.3 | Run reproduces from recorded commands | NOT STARTED | — | — |

---

## Decisions log

| # | Subject | Status | Ruling summary | Where recorded |
|---|---|---|---|---|
| D1 | Contracts C1–C4 | APPROVED IN PRINCIPLE, with amendments + B review | C1 Code+History, canonical IDs, hashes separate, inferred marked; C2 provenance+revision+failure semantics; C3/C4 coordinated with B before implementation/finalization | Decision record above; `contracts/*.json`; audit §6 |
| D2 | Package layout | APPROVED | `src/tracefix/` | audit §3; `pyproject.toml` |
| D3 | Target repository | PENDING — candidates proposed | `psf/requests` recommended; `pylint`, `pytest` alternatives; no ingestion until selected | audit §10; A0.11 |
| D4 | Tokenizer | APPROVED WITH CONDITION | Configurable interface committed in C3 draft; tiktoken only if model-compatible; encoding + estimate status recorded | `contracts/context_manifest.json` token_accounting |
| D5 | Spec PDF in repo | APPROVED | Committed at `docs/project/tracefix-proposed-project-report.pdf` (team-authored draft) | audit §1.4 |
| D6 | Tooling / Docker honesty | APPROVED | `.venv` + pytest/ruff/mypy committed; integration marker-gated; no real-integration claims while Docker down | `pyproject.toml`; audit §4 |
| D7 | DBSF | APPROVED (RRF first) | DBSF deferred until authoritative definition cited | audit §7 Phase 4; A4.2 |
| D8 | Evaluation dataset + metric rules | PENDING | Proposal: SWE-bench case set on selected repo with contamination disclosure, or BugsInPy alternative; metric rules drafted in C4 | audit §10; `contracts/evaluation.json` |

---

## Session log

| Date | Session outcome | Completed | Not completed | Tests run (actual) | Deviation | Next task |
|---|---|---|---|---|---|---|
| 2026-10-16 | Phase 0 audit produced; branch `suhaas` created | A0.1–A0.4, A0.6, A0.7 | A0.5 awaiting review; no implementation | none — no test infrastructure existed yet (pytest not installed) | Branch model `suhaas` → `main` instead of brief §8 `feature/graph-retrieval` (instructed; audit §8) | A0.5 decisions |
| 2026-10-16 | Checkpoint 0 decisions recorded; contracts revised to C1 v0.2.0 / C2 v0.2.0 and C3/C4 drafts; tooling + contract tests landed | A0.5 (DONE), A0.8, A0.9, A0.12 | A0.10 and A0.11 BLOCKED (B not in repo; D3 unselected); Phase 1 not started | `.venv/bin/pytest -q` → **15 passed in 0.01s** (exit 0); `.venv/bin/ruff check .` → **All checks passed!** (exit 0, after fixing 5 E501 findings from the first run); `.venv/bin/mypy` → **Success: no issues found in 1 source file** (exit 0) | None | A0.10 (B review of Q-B1–Q-B12) and A0.11 (D3 selection); A1.1 unblocked only after C1 finalization |

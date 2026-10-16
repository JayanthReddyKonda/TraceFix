# Workstream A — Task Ledger

Graph/retrieval workstream plan. Maintained per brief §11: updated at the start and
end of every session; a task is `DONE` only when its acceptance criteria are met and
evidence is recorded.

- Owner: Workstream A (graph + retrieval + context)
- Primary branch: `suhaas` — integration target: `main`
- Latest checkpoint decision: **Checkpoint 0 pending** (proposed 2026-10-16, awaiting integration-owner ruling on `docs/workstreams/graph-retrieval-audit.md` §9)
- Session rule: pick the highest-priority `NOT STARTED` task whose dependencies are all `DONE`.

Statuses used: `NOT STARTED`, `IN PROGRESS`, `BLOCKED`, `READY FOR REVIEW`, `DONE`.

---

## Phase 0 — Audit and structure plan

| ID | Task | Description / rationale | Dependencies | Acceptance criteria | Owner | Status | Tests & evidence | Files changed | Follow-up |
|---|---|---|---|---|---|---|---|---|---|
| A0.1 | Repository audit | Inspect tree, git state, entry points, deps, tests, contracts, FalkorDB setup, fixtures | none | Audit report covers all 8 brief §5 audit items with commands and observed outputs | WSA | DONE | Command outputs recorded in audit §1.1–1.3 (empty repo, no contracts/tests, docker daemon down, no pytest/falkordb) | `docs/workstreams/graph-retrieval-audit.md` | Re-audit if another workstream lands code |
| A0.2 | Spec extraction | Extract the only project artifact (proposed report PDF) into reviewable text | none | Spec facts labeled `[spec]`, not presented as implementation | WSA | DONE | 16-page PDF extracted; citations recorded in audit §1.4 | audit §1.4 | Decide whether to commit PDF copy (decision D4) |
| A0.3 | Target structure proposal | Propose module tree adapted to empty repo; reconcile brief layout vs spec §13 | A0.1, A0.2 | Structure, mapping, and "not created yet" rationale documented | WSA | DONE | audit §3 | audit §3 | Approval decision D2 |
| A0.4 | Dependency & risk analysis | Propose runtime/dev deps from observed toolchain; enumerate risks with mitigations | A0.1 | Every proposed dep justified; every risk has owner/mitigation | WSA | DONE | audit §4, §5 (R1–R11) | audit §4, §5 | Decisions D4–D6 |
| A0.5 | Contract proposals C1–C4 | Propose graph schema, retrieval, context manifest, evaluation contracts | A0.1, A0.2 | All four proposed with open questions flagged; no contract code written | WSA | READY FOR REVIEW | audit §6 | audit §6 | **Checkpoint 0 approval (blocker for Phase 1)** |
| A0.6 | Phase-by-phase plan + task ledger | Sequence phases with acceptance evidence and checkpoint stops | A0.3–A0.5 | Plan table with checkpoint mapping; ledger exists | WSA | DONE | audit §7–§9; this ledger | audit §7–§9, this file | Update after every checkpoint |
| A0.7 | Branch/merge setup | Primary `suhaas`, integration on `main` | none | Branch created; work confined to `suhaas` | WSA | DONE | `git branch` shows `suhaas`; recorded as instructed deviation in audit §8 | n/a (git state) | Merge to `main` at integration |

---

## Phase 1 — Graph schema and repository ingestion  *(blocked on Checkpoint 0)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A1.1 | Contract tests for `contracts/graph_schema.json` | D1 | Serialized sample graph validates; invalid graph rejected | NOT STARTED | — | — |
| A1.2 | `graph/models.py` + `graph/schema.py` | A1.1 | Typed entities/relations with provenance (`observed`/`inferred`) and revision fields | NOT STARTED | — | — |
| A1.3 | `graph/client.py` (FalkorDB connection, timeout, error mapping) | D6 | Connection failures/timeouts raise typed errors; no free Cypher escapes this layer | NOT STARTED | — | — |
| A1.4 | Python AST ingestion (files, modules, classes, functions, imports, calls) | A1.2 | Parse fixtures pass; malformed input tolerated and reported | NOT STARTED | — | — |
| A1.5 | Git history ingestion (commits, authors, file changes) | A1.2 | Missing/shallow history yields explicit `history_available: false` | NOT STARTED | — | — |
| A1.6 | Test detection + `COVERED_BY` heuristic | A1.4 | Heuristic documented as `inferred` with stated confidence | NOT STARTED | — | — |
| A1.7 | Idempotent ingestion + revision stamping | A1.4, A1.5 | Re-ingest same revision → no duplicates; different revision → new snapshot | NOT STARTED | — | — |
| A1.8 | Parser limitations doc | A1.4–A1.6 | `docs/graph/` lists unsupported constructs and confidence per relation | NOT STARTED | — | — |

## Phase 2 — Bounded graph query layer  *(blocked on A1.x + FalkorDB availability)*

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
| A3.4 | Dense adapter (feature-flagged, off by default) | A3.1, D6 | Skipped without model; never downloads in default test run | NOT STARTED | — | — |
| A3.5 | `context_selector.py` (token budget, source diversity) | A3.1–A3.3 | Budget never exceeded; selection reason per item | NOT STARTED | — | — |

## Phase 4 — Score fusion  *(blocked on A3.1)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A4.1 | RRF with deterministic golden tests | A3.1 | Known ranks → expected scores | NOT STARTED | — | — |
| A4.2 | DBSF **only** with cited authoritative definition recorded in-repo | D7 | Source cited before code; name not used for a substitute formula | NOT STARTED | — | — |
| A4.3 | Fusion method selectable in config | A4.1 | Config switch changes results; both arms measurable | NOT STARTED | — | — |

## Phase 5 — Context manifest and provenance  *(blocked on A3, A4; contract sign-off by repair owner)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A5.1 | Contract tests for `contracts/context_manifest.json` | D1 (C3) | Valid manifest accepted; missing provenance rejected | NOT STARTED | — | — |
| A5.2 | `retrieval/manifest.py` (stable evidence ids, token estimates, serialization) | A5.1, A3.5 | Round-trip serializes; token counts labeled estimate + tokenizer | NOT STARTED | — | — |
| A5.3 | Budget accounting + duplicate/source-coverage stats | A5.2 | Totals match itemized costs; duplicates counted, not silently dropped | NOT STARTED | — | — |

## Phase 6 — Retrieval evaluation  *(blocked on A5 + dataset decision D8)*

| ID | Task | Dependencies | Acceptance criteria | Status | Tests & evidence | Files changed |
|---|---|---|---|---|---|---|
| A6.1 | Case-set loader validating `contracts/evaluation.json` | D1 (C4), D8 | Invalid/unlocalizable cases handled per declared rules | NOT STARTED | — | — |
| A6.2 | Metrics: Hit@k, Recall@k, rank of fixed function, tokens, latency, counts, duplicates | A6.1 | Denominators declared; no metric without a reproducible run | NOT STARTED | — | — |
| A6.3 | Baseline-vs-graph-guided comparison runner | A3.x, A6.2 | One command runs both arms on same case set, writes config+revision metadata | NOT STARTED | — | — |
| A6.4 | First recorded experiment in `docs/experiments/` | A6.3 | Run reproduces from recorded commands | NOT STARTED | — | — |

---

## Decisions log (Checkpoint 0 — integration owner)

| # | Decision | Options | Proposal | Status |
|---|---|---|---|---|
| D1 | Approve contracts C1–C4 (audit §6) incl. C1 open questions | approve / amend / reject | approve C1–C4; start schema with Code+History layers, add Service node only if target repo is multi-service | PENDING |
| D2 | Package layout: `src/tracefix/*` (brief) vs flat `ingest/`, `context/` (spec §13) | src-layout / flat | src-layout, mapping recorded in audit §3 | PENDING |
| D3 | Target repository for ingestion + evaluation dataset | — | needed before A1.4 has real input; not yet named | PENDING |
| D4 | Tokenizer for budget accounting | tiktoken cl100k / len÷4 heuristic | tiktoken, all counts marked estimated | PENDING |
| D5 | Commit spec PDF into `docs/project/` | yes / no | yes (438 KB, traceability) | PENDING |
| D6 | Test/dependency environment | project `.venv` + pytest/ruff/mypy; Docker for FalkorDB | `.venv`; integration tests marker-gated until daemon runs | PENDING |
| D7 | DBSF in Phase 4 | implement with cited source / RRF only | RRF first; DBSF only with in-repo cited definition | PENDING |
| D8 | Evaluation dataset + metric denominators (spec §11) | owned by integration owner | required before Phase 6 | PENDING |

---

## Session log

| Date | Session outcome | Completed | Not completed | Tests run (actual) | Deviation | Next task |
|---|---|---|---|---|---|---|
| 2026-10-16 | Phase 0 audit produced; branch `suhaas` created | A0.1–A0.4, A0.6, A0.7 | A0.5 awaiting review; no implementation | none — no test infrastructure exists yet (pytest not installed) | Branch model `suhaas` → `main` instead of brief §8 `feature/graph-retrieval` (instructed by user; recorded in audit §8) | D1–D8 decisions, then A1.1 |

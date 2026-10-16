# Workstream A — Repository Intelligence, Graph, Retrieval & Context

## Phase 0 Audit Report

- Status: `BLOCKED — NEEDS DECISION` (Checkpoint 0 — contracts approval required)
- Branch: `suhaas` (primary), integration target `main`
- Date: 2026-10-16
- Author: Workstream A (graph + retrieval + context owner)

---

## 1. Audit scope and method

Every statement below is an observation from a command run in this session, or an
explicitly labeled proposal. Nothing in this report is inferred from assumed
structure.

### 1.1 Repository state

| Item | Observation | Command |
|---|---|---|
| Working tree | `/Users/suhaas/TraceFix`, only `.git/` present before this phase | `ls -la` |
| Commits | none (empty clone) | `git log --oneline` → `fatal: your current branch 'main' does not have any commits yet` |
| Branches | `main` (unborn), `suhaas` (created this session) | `git branch -a` |
| Uncommitted changes | none at audit time | `git status` |
| Remote | `origin` → `https://github.com/karnam-ui/TraceFix.git` | `git remote -v` |
| Remote content | `gh repo view karnam-ui/TraceFix` → exists, **empty repository** | `gh` CLI, auth as `karnam-ui` |
| Other workstreams present | none found under `karnam-ui` or in the local filesystem | `gh repo list karnam-ui`; `find /Users/suhaas -maxdepth 4 -iname "*tracefix*"` |
| Git identity | `Suhaas <24071A66C9@vnrvjiet.in>` | `git config user.name/user.email` |

**Conclusion: there is no pre-existing code, contract, test, configuration, or
documentation to preserve.** Rule 4.2 (preserve existing work) is satisfied
vacuously; every artifact described here is a proposal, not a modification.

### 1.2 Existing application entry points, dependency management, tests

| Item | Observation |
|---|---|
| Python package config (`pyproject.toml`, `setup.py`, `requirements.txt`) | absent |
| Frontend config (`package.json`) | absent |
| Test suites / test commands | absent; no `pytest` installed in the active interpreter |
| Lint/type config (`ruff.toml`, `mypy.ini`) | absent |
| CI workflows | absent (`.github/` absent) |
| Shared contracts / architecture docs in repo | absent |
| FalkorDB setup (docker-compose, scripts) | absent |
| Ingestion / retrieval implementation | absent |
| Sample repositories, incident cases, evaluation fixtures | absent |

### 1.3 Toolchain observed on this machine

| Tool | Version / state |
|---|---|
| `python3` | 3.13.12 at `/opt/miniconda3/bin/python3` (conda `base`) |
| `pip` | 26.2.1 |
| `git` | 2.39.5 (Apple Git-154) |
| `docker` | 29.1.3 installed, **daemon not running** (`connect to docker.sock … no such file`) |
| `node` / `npm` | v24.12.0 (relevant only to UI owner) |
| `ruff` | 0.15.8 at `/Library/Frameworks/Python.framework/Versions/3.14/bin/ruff` |
| `mypy` | 1.19.1 at `/Library/Frameworks/Python.framework/Versions/3.14/bin/mypy` |

Python import probe against the active interpreter:

| Module | Present | Module | Present |
|---|---|---|---|
| `networkx` | yes | `pytest` | **no** |
| `rank_bm25` | yes | `falkordb` | **no** |
| `numpy`, `pandas`, `scipy` | yes | `redis` | **no** |
| `pydantic` | yes | `tiktoken` | **no** |
| `sentence_transformers` | yes | `GitPython` (`git`) | **no** |
| `matplotlib` | yes | `fastapi` | **no** (owned by integration) |
| `httpx`, `yaml` | yes | `tree_sitter` | **no** (intentionally deferred) |

Other interpreters available: pyenv `3.11.4`, pyenv `sih-311`, conda env `tardis`.
None is TraceFix-specific.

### 1.4 Project specification source

The only existing TraceFix artifact on this machine is:

`/Users/suhaas/Downloads/TraceFix Graph-Native Bug-Resolution Agent - Proposed Project Report.pdf`
(16 pages, draft v1, "Graph Hacks: Context for AI Agents (WeMakeDevs x FalkorDB,
Oct 15–18, 2026)").

Its text was extracted for this audit. Facts taken from it (labeled **[spec]**,
not verified implementations):

- **[spec]** Stack: Python for ingestion/agents/MCP/evaluation, FastAPI, FalkorDB via
  Docker with official Python client, React UI, pytest in network-disabled Docker.
- **[spec]** Graph model layers: Code (Service, File, Class, Function, Test), History
  (Commit, Person, Team), Knowledge, Decision, Incident, Procedural, Agent-state.
  Edges include `CALLS`, `IMPORTS`, `DEFINED_IN`, `COVERED_BY`, `MODIFIED_IN`,
  `AUTHORED_BY`, `OWNED_BY`, `KNOWS`, `AFFECTS`, `RESOLVED_BY`, `INSTANCE_OF`,
  `PROMOTED_TO`, `SOURCE`, `REQUIRES`.
- **[spec]** Temporal handling: `commit_sha` + `content_hash` on code-derived
  nodes/edges; invalidation on change; `valid_to` instead of deletion.
- **[spec]** Multi-tenancy: one FalkorDB graph per tenant.
- **[spec]** Retrieval: stack-trace frames/identifiers → keyword → embeddings as
  fallback; expansion bounded (default 2 hops) and type-filtered; candidates scored
  by graph distance, recency, test coverage, incident links; assembly under a token
  budget; explicit stopping rule.
- **[spec]** Evaluation arms: A (BM25 whole-file/repo), B (graph, no memory),
  C (graph + episodic memory), D (graph + memory + playbooks). Metrics: localization
  hit at function/file level, tokens loaded, fix pass rate, learning curve.
- **[spec]** Dataset: 30–60 chronological real bugs from 1–2 Python repos (primary),
  10 seeded bugs (demo).
- **[spec]** §17 lists unverified assumptions: FalkorDB feature set, hackathon rules,
  licensing, model costs.
- **[spec]** §13 proposes a repo layout (`ingest/`, `graph/`, `context/`, `eval/`, …)
  that differs from the layout mandated by the Workstream A brief
  (`src/tracefix/graph/`, `src/tracefix/retrieval/`). **This conflict is a Checkpoint 0
  decision — see §6.**

The PDF is committed at `docs/project/tracefix-proposed-project-report.pdf`
(Checkpoint 0 decision D5). Authorship is the project team's own draft, so
redistribution inside this repository is at the project's discretion; if any
third-party material is later identified inside it, remove or replace it.

---

## 2. Gap analysis (spec → what exists)

| Spec requirement | Exists today | Gap |
|---|---|---|
| FalkorDB instance + per-tenant graphs | nothing | Docker daemon not running; `falkordb` client not installed; no compose file |
| Code/history ingestion | nothing | entire Phase 1 |
| Typed bounded graph queries | nothing | entire Phase 2 |
| Lexical / dense / graph-guided retrieval | nothing | entire Phase 3 |
| Score fusion (RRF, DBSF) | nothing | entire Phase 4 |
| Context manifest + provenance | nothing | entire Phase 5 |
| Evaluation harness | nothing | entire Phase 6; also depends on dataset selection |
| Shared contracts (`contracts/*`) | nothing | **Checkpoint 0 blocker** |
| Test infrastructure | nothing | no pytest, no fixtures, no markers |
| Second developer / integration owner in repo | not present | coordination model (§8) |

---

## 3. Proposed target structure

Proposal (adapted from the brief's structure; repo is empty, so nothing is being
replaced). This is the Workstream A footprint only — other workstreams own their
own directories.

```text
contracts/                          # shared, versioned, machine-readable
  graph_schema.json                 # node labels, edge types, required/optional props
  retrieval.json                    # strategy config + ranked-result schema
  context_manifest.json             # provenance manifest schema
  evaluation.json                   # case schema, metric definitions, denominators

src/tracefix/
  __init__.py
  graph/
    models.py                       # dataclasses/pydantic: entities, relations, provenance
    schema.py                       # contract-backed schema constants + validators
    client.py                       # FalkorDB connection, retries, timeouts, tx helper
    ingestion.py                    # Python AST + git history -> entities/relations
    queries.py                      # typed, parameterized, bounded query operations
  retrieval/
    interfaces.py                   # RetrievalStrategy protocol, RankedItem, Query
    lexical.py                      # deterministic BM25/keyword baseline
    dense.py                        # optional embedding adapter (feature-flagged)
    graph_guided.py                 # bounded expansion from seed evidence
    fusion.py                       # RRF (+ DBSF only if spec-verified)
    context_selector.py             # budgeted selection, diversity rules
    manifest.py                     # evidence IDs, token estimates, serialization

tests/
  unit/graph/  unit/retrieval/
  contract/                            # validates serialized objects against contracts/
  integration/graph/                   # requires FalkorDB (marker: integration)
  fixtures/                            # tiny synthetic Python repos + bug cases

scripts/
  ingest_repository.py
  evaluate_retrieval.py

docs/
  workstreams/graph-retrieval-audit.md   # this file
  workstreams/graph-retrieval-plan.md    # task ledger
  graph/          retrieval/       # module docs, limitations, parser confidence
  experiments/    # run configs + recorded results
  project/        # (optional) copy of the spec PDF — pending decision

pyproject.toml                       # package metadata, deps, pytest/ruff/mypy config
```

**Reconciliation with spec §13 (`ingest/`, `context/`, …):** the brief mandates
`src/tracefix/graph|retrieval`; the PDF proposes flat `ingest/`, `context/`.
Proposal: adopt the src-layout above (it is what Workstream A's brief specifies, it
keeps import hygiene, and it houses both concerns); document the mapping
`spec ingest/ → tracefix.graph.ingestion`, `spec context/ →
tracefix.retrieval.context_selector`. The integration owner may override this at
Checkpoint 0 before any code exists — cost of changing now is zero.

Deliberately **not** created yet: `docs/architecture/`, `docs/experiments/`,
empty package directories. Directories are created with their first real file.

---

## 4. Dependencies

### 4.1 Runtime (proposed, all pinned in `pyproject.toml`)

| Dependency | Why | Justification status |
|---|---|---|
| `falkordb` | official FalkorDB Python client **[spec §10]** | required; not installed |
| `pydantic` ≥2 | contract validation, manifest serialization | already available |
| `GitPython` or `subprocess` git | commit/file-change history for ingestion | proposal: `subprocess` (no new dep, git is guaranteed) |
| `networkx` | offline/in-memory graph for unit tests & fixtures without Docker | already available; test-only scope, FalkorDB remains system of record |
| `rank_bm25` | deterministic lexical baseline **[spec arm A]** | already available; fallback: own BM25 if API issues |
| `tiktoken` | token-cost estimation for the budget | **not installed**; fallback documented below |
| `numpy` | score normalization | already available |

### 4.2 Dev / quality (proposed)

`pytest`, `pytest-timeout`, `pytest-cov` (or none), `ruff`, `mypy`. `ruff` 0.15.8 and
`mypy` 1.19.1 exist system-wide; `pytest` does not exist anywhere on this machine
(`~/.pytest_cache` exists, so some interpreter once had it — the active one does
not).

**Environment proposal:** create a project venv `.venv` (Python 3.11 via pyenv or
3.13 via conda) rather than installing into conda `base`. `.venv/` goes in
`.gitignore`. Installing into `base` would be a shared-machine side effect and is
not proposed.

### 4.3 Tokenizer decision (needs ruling)

No tokenizer is installed. Options:

1. `tiktoken` `cl100k_base` — closest to real LLM cost, one new dependency.
2. `len(text) / 4` heuristic — zero deps, cruder.

Proposal: **option 1**, with every count labeled `estimated: true` and the encoding
name recorded in the manifest; option 2 as an offline fallback for the offline-CI
marker. Decision needed because Phase 5's manifest schema embeds the tokenizer id.

### 4.4 Services

FalkorDB via Docker **[spec §10]**. Blocker: the Docker daemon is not running on
this machine, so no integration test can execute right now. Consequence for test
policy: unit/contract tests must run with **no services**; FalkorDB tests are gated
behind an `integration` marker and a documented startup command.

---

## 5. Risks

| # | Risk | Impact | Mitigation / status |
|---|---|---|---|
| R1 | Docker daemon down; FalkorDB unverified | Phases 1–2 integration blocked; spec §17 already flags FalkorDB features as unverified | Write client behind `GraphClient` interface; unit-test against a fake + in-memory graph; verify FalkorDB version, Cypher subset, timeout support before Phase 2 acceptance |
| R2 | No shared contracts exist | Everything downstream is speculative | **Checkpoint 0** — this report + `graph-retrieval-plan.md` propose them; no dependent code until approved |
| R3 | Spec layout conflict (§13 vs brief) | Rework if decided late | Decide at Checkpoint 0, cost is zero today |
| R4 | No evaluation dataset selected; ground truth undefined | Phase 6 unrunnable; evaluation definitions are explicitly **not** Workstream A's to define | Dataset + denominators must come from the integration owner; Phase 6 task stays `BLOCKED` until `contracts/evaluation.json` exists |
| R5 | Single-developer repo; brief assumes two workstreams + integration owner | Checkpoint approvals have no second party in-repo | Treat the human user as integration owner; approvals recorded as commits/comments in `docs/workstreams/`; never infer approval from silence |
| R6 | Static call graph misses dynamic dispatch/monkey-patching | Overstated graph quality | Document parser confidence per relationship type; mark inferences vs observed; never claim completeness (brief §6 Phase 1) |
| R7 | Git history may be shallow/absent in target repos | `MODIFIED_IN`/`OWNED_BY` missing | Ingestion records `history_available: false` explicitly rather than emitting empty relationships |
| R8 | Token cost without tokenizer installed | Fabricated budget numbers (explicitly forbidden) | §4.3 decision; until decided, manifest emits `token_estimate` only with method label, never a bare number |
| R9 | Model contamination / dataset licensing **[spec §17]** | Evaluation validity | Out of Workstream A's ownership; flagged for integration owner |
| R10 | DBSF formula not located in spec | Wrong-but-labeled implementation | Phase 4 rule: no DBSF code until an authoritative definition is cited in-repo; RRF ships first |
| R11 | Dense retrieval (sentence_transformers present) pulls large model artifacts | Repo bloat, nondeterminism | Feature-flagged, excluded from default test run, models never committed (§8 Git discipline) |

---

## 6. Shared contracts (revised after Checkpoint 0, decision D1)

Approved in principle with amendments; the machine-readable files live in
`contracts/` and are locked by `tests/contract/`. C1 and C2 are
`approved-in-principle`. C3 and C4 are drafts blocked on Workstream B review;
their open questions are recorded inside the contract files (Q-B1–Q-B12).

**C1 — `contracts/graph_schema.json` (v0.2.0, approved-in-principle)**
Active layers: Code + History only — nodes `Repository`, `File`, `Module`,
`Class`, `Function`, `Test`, `Commit`, `Person`; edges `CONTAINS`, `IMPORTS`,
`CALLS`, `COVERED_BY`, `MODIFIED_IN`, `AUTHORED_BY`, `OWNED_BY`. Deferred:
Knowledge, Decision, Incident, Procedural, Agent-state layers and
`AFFECTS`/`RESOLVED_BY` (incident-memory lifecycle is Workstream B's; add via the
contract-change procedure). Amendments per D1: stable canonical `entity_id`
(`<repo_url>#<kind>:<qualified_key>`), revision-independent; `revision` and
`content_hash` are node properties only; every edge declares `provenance`
∈ {observed, inferred} plus `source`, with `confidence` required on inferred
edges. Unresolvable imports become a File `imports_declared` property, never a
fabricated edge. Formerly open questions are resolved: start with Code+History;
`Service` node deferred until a multi-service target repo exists.

**C2 — `contracts/retrieval.json` (v0.2.0, approved-in-principle)**
`RetrievalStrategy.retrieve(query) -> RetrievalResult`. Amendments per D1: every
`RankedItem` carries `provenance`, `source_revision`, and `source`; results carry
explicit failure/partial semantics — `complete`, `partial_reason`
(`limit_reached | timeout | index_incomplete | graph_unavailable |
strategy_error_recovered`) and a typed `failure` object; a strategy raises
`RetrievalError` only when it can return zero usable items. Query bounds: `k`,
`limits.max_items`, `limits.max_hops`, `limits.timeout_ms`. Determinism required
except dense strategies, which must record model and seed.

**C3 — `contracts/context_manifest.json` (v0.1.0-draft — blocked on Workstream B)**
Proposed fields: run/case/repo/revision; `budget {token_limit, tokenizer,
estimated}`; `strategy_config`; `items[]` with evidence_id, type,
path/symbol/lines, strategy/rank/score, graph_path/expansion_explanation,
selection_reason, token_contribution, provenance, source; `totals {tokens,
item_count, duplicates}`. Token accounting is a configurable tokenizer interface
per D4: every figure is either named-tokenizer-measured or labeled
`estimated: true`. **Blocked on B:** Q-B1 budget ownership, Q-B2 budget scope
(evidence-only vs including repair scaffolding), Q-B3 tokenizer/model
compatibility, Q-B4 evidence_id cross-run stability (certificate/ablation
reuse), Q-B5 transport, Q-B6 raw content by hash vs inlined.

**C4 — `contracts/evaluation.json` (v0.1.0-draft — blocked on Workstream B)**
Case record: case_id, repo, revision, bug_report, ground_truth_files/functions,
localizable + excluded_reason, dataset_source/instance_id, fix_commit,
fail_to_pass_tests. Metrics with declared denominators: Hit@k/Recall@k over
localizable cases only; unlocalizable cases tallied with reasons, never dropped
silently; arms comparable only on identical case-set fingerprints (sha256 over
sorted (case_id, revision) pairs + contract version). **Blocked on B:** Q-B7
ground-truth derivation, Q-B8 primary k values, Q-B9 file-level metrics, Q-B10
fingerprint method, Q-B11 multi-function any-hit vs all-hit, Q-B12 initial
dataset choice.

---

## 7. Phase-by-phase implementation plan (post-approval)

Each phase ends with a mandatory stop (brief §10). No phase begins before the
previous checkpoint is explicitly approved.

| Phase | Scope | Acceptance evidence | Checkpoint after |
|---|---|---|---|
| **0** (this report) | Audit, target structure, contracts proposal, task ledger | This doc + `graph-retrieval-plan.md` committed; status reported | **Checkpoint 0 — BLOCKED — NEEDS DECISION** |
| **1** Graph schema + ingestion | `models.py`, `schema.py`, `client.py`, `ingestion.py`; Python AST + git history; idempotent, revision-aware, error-tolerant | Unit tests: schema validation, parse fixtures, malformed input, duplicate ingestion, revision handling; docs of parser limitations | Checkpoint 1 |
| **2** Bounded query layer | `queries.py`: typed ops (symbol lookup, file defs/imports, bounded neighborhood, covering tests, commit/incident relations); limits on depth/count/time; no free Cypher | Unit tests (limits, params, empty, invalid, db errors) + FalkorDB integration tests against pinned version | Checkpoint 1 |
| **3** Retrieval strategies | `interfaces.py`, `lexical.py`, `graph_guided.py`, `dense.py` (flagged), `context_selector.py` | Per-strategy unit tests, deterministic fixtures, expansion limits, budget enforcement | Checkpoint 2 input |
| **4** Score fusion | `fusion.py`: RRF verified by deterministic tests; DBSF only with cited authoritative source | Golden-value tests; method selectable in config | Checkpoint 3 |
| **5** Manifest + provenance | `manifest.py`, contract tests vs `context_manifest.json` | Serialization round-trip, bounded output, budget accounting, no fabricated counts | Checkpoint 2 |
| **6** Evaluation | `scripts/evaluate_retrieval.py`, baseline-vs-graph comparison, deterministic runs with config+revision metadata | Reproducible run recorded in `docs/experiments/`; Hit@k/Recall@k/latency/token metrics with declared denominators | Checkpoint 3 |

Dependency rule: Phases 1–2 block 3 (graph-guided needs queries); Phase 3 and Phase 4
partially parallel (fusion needs only ranked lists); Phase 5 needs 3+4; Phase 6 needs
5 **and** the external dataset decision.

Testing matrix to be maintained (brief §7):

| Layer | Workstream A coverage |
|---|---|
| Unit | AST parsing, ranking, fusion math, budget selection, validators |
| Contract | serialized graph/retrieval/manifest objects vs `contracts/*.json` |
| Integration | FalkorDB client + queries against a live instance (marker-gated) |
| Regression | re-fix defects under `tests/unit/**` |
| Evaluation | reproduce declared runs on the frozen case set |
| Failure-path | DB timeout/refusal, missing git history, malformed source, budget exhaustion |

---

## 8. Coordination and Git model

- Primary branch: **`suhaas`** (Workstream A work happens here only).
- Integration: merge `suhaas` → `main`; `main` is the stable accepted state.
- Worktree: this directory is exclusively Workstream A's; no shared mutable checkout.
- Ownership guard: Workstream A touches `contracts/` (via proposal), `src/tracefix/graph/`,
  `src/tracefix/retrieval/`, `scripts/ingest_repository.py`,
  `scripts/evaluate_retrieval.py`, `tests/{unit,contract,integration}/{graph,retrieval}/`,
  `docs/workstreams/`, `docs/graph/`, `docs/retrieval/`, `docs/experiments/`.
  It must not edit agent/sandbox/UI/API modules owned by others.
- **Deviation from brief §8:** the brief recommends `feature/graph-retrieval` /
  `feature/repair-evaluation` / `integration`. Only Workstream A exists in this repo
  today, and the instructed workflow is `suhaas` → `main`. Recorded here as a
  deliberate, instructed deviation (brief §11 requires deviations be logged). If
  other contributors appear, rename/re-branch through the integration owner before
  any shared commit history diverges.
- No secrets, no `.venv`, no model weights, no FalkorDB dumps committed.

---

## 9. Checkpoint 0 checklist — resolution status

1. Contracts C1–C4: **resolved in principle** (D1). C1/C2 revised and committed;
   C3/C4 drafts committed, blocked on Workstream B (Q-B1–Q-B12).
2. Package layout: **approved** (D2) — `src/tracefix/`.
3. Target repositories: **candidates proposed** (§10); selection pending (D3).
4. Tokenizer: **approved with condition** (D4) — configurable interface committed
   in C3; tiktoken `cl100k_base` only if compatible with the selected model.
5. Spec PDF: **approved and committed** (D5) — `docs/project/`.
6. Tooling: **approved and set up** (D6) — project `.venv`; integration tests
   marker-gated; no real-integration claims while Docker is unavailable.
7. Branch model: **in use** — `suhaas` → `main` (§8).
8. DBSF: **deferred** (D7) — RRF first; DBSF only with a cited authoritative
   definition.
9. Evaluation dataset and metric rules: **pending** (D8) — proposal in §10, to be
   finalized with Workstream B.

## 10. Target repository candidates (D3) and evaluation-dataset proposal (D8)

Repository facts verified via `gh api repos/<repo>` on 2026-10-16. SWE-bench
instance counts are the paper's post-validation counts (arXiv:2310.06770).

| Candidate | Repo size | Code lines (SWE-bench paper) | License | SWE-bench instances | Notes |
|---|---|---|---|---|---|
| `psf/requests` — recommended | 13.6 MB | ~30k | Apache-2.0 | 44 | Smallest graph; active (last push 2026-09-28); pytest suite; permissive license; edge spot-checks feasible by hand |
| `pylint-dev/pylint` | 42.2 MB | ~109k | GPL-2.0 | 57 | Rich internal call structure (exercises CALLS/IMPORTS); GPL is acceptable for evaluation-only use |
| `pytest-dev/pytest` | 42.1 MB | ~111k | MIT | 119 | Highest instance count of the small/medium set; heavier sandbox story for Workstream B |

`pallets/flask` (12.2 MB, BSD-3-Clause) was considered and rejected: only 11
validated instances, too few for a 30–60 bug stream.

**D3 proposal:** ingest `psf/requests` first as the Phase 1 target (fast, full
history since 2011, small enough to audit extracted edges manually). Evaluation
pool: its 44 SWE-bench instances, extendable with `pylint`'s 57 if a larger case
set is wanted.

**D8 proposal (for joint decision with Workstream B):** case set = SWE-bench
instances for the selected repository at their recorded base commits; ground
truth = functions enclosing gold-patch hunks (pending Q-B7); report Hit@k at
k ∈ {5, 10, 20} (pending Q-B8). Contamination policy: SWE-bench issues/PRs are
mostly ≤2023, i.e. pre-cutoff for current models; per spec §16 every reported
result must state how many cases are pre-cutoff. Alternative if post-cutoff bugs
are required: BugsInPy (493 real bugs across 17 Python projects, ACM FSE 2020;
each bug ships buggy + fixed commits and an exposing test; a 2024 reproduction
study revalidated 67% unmodified and >95% after environment fixes; projects
include `black`, `httpie`, `tornado`, `scrapy`, `fastapi`). Workstream B should
choose between the larger, well-trodden SWE-bench set with contamination
disclosure and a smaller BugsInPy set with per-bug environments.

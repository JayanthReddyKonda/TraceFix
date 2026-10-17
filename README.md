# TraceFix

TraceFix is a graph-native bug-resolution agent. This repository contains
**Workstream A**: repository intelligence (schema, ingestion, typed graph query),
retrieval (lexical baseline, graph-guided expansion, optional dense adapter,
RRF fusion pipeline), token-budgeted context selection, a context manifest, and
the evaluation infrastructure used for controlled retrieval studies.

## Status and scope

Workstream A is an in-progress research component. It does **not** claim
retrieval or repair quality improvements. The graph contracts
(`contracts/graph_schema.json`, `contracts/retrieval.json`) are approved in
principle; the context-manifest and evaluation contracts are still drafts
(`*-draft`, pending coordination with the repair/sandbox owner), and no
evaluation metric defaults are approved. Live FalkorDB integration is not
verified in this environment (Docker unavailable).

## Layout

```
src/tracefix/graph/       # model, schema, client, ingestion, typed query, providers
src/tracefix/retrieval/   # interfaces, lexical, graph-guided, dense, fusion, pipeline,
                          # context_selector, manifest
src/tracefix/evaluation/  # case-set loader, pure metrics, single-arm runner
contracts/                # versioned JSON contracts
eval/cases/               # frozen candidate case set (read-only)
scripts/                  # case-set validator
docs/                     # component docs, workstream ledger, experiment template
tests/                    # unit + contract tests (service-free)
```

## Install

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
# optional exact tokenizer
pip install -e ".[tiktoken]"
```

## Test and quality gates

```sh
pytest -q
ruff check .
mypy
```

Tests are service-free by default: integration tests requiring a running
FalkorDB are marked `integration` and excluded unless explicitly selected.

## Evaluation

`src/tracefix/evaluation/` loads the frozen case set read-only, computes pure
metrics with explicit denominators, and runs **one** retrieval arm at a time
(strategy dependencies are injectable, so no Docker/FalkorDB/network is needed).
Ground truth in the candidate set is provisional; provenance of the raw dataset
rows is unverified. Results are a *controlled study*, not a benchmark.

See `docs/experiments/TEMPLATE.md` for the required report format.

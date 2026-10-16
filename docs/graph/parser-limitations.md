# Graph parser limitations (A1.8)

Scope: `src/tracefix/graph/ingestion.py` — Python AST + git history → C1 nodes and
edges. Every limitation below is also returned on `IngestionResult.limitations`
so downstream consumers can surface it rather than assume full coverage.

## Node extraction

- **Local (nested) function definitions are not extracted.** Only module-level
  functions, methods, and one level of nested classes are emitted.
- **Classes/functions defined inside `if`/`try`/`with` blocks are extracted**
  (the AST walker visits all statement bodies), but their `CONTAINS` parent is
  the enclosing module/class, not the conditional block.
- Repository, File, and Module nodes are always emitted per source file. A file
  that fails to parse still gets a `File` node (with `imports_declared: []`) and
  the parse error is recorded in `parse_errors`.
- File source that is not valid UTF-8 is reported as `unreadable` in
  `parse_errors` and skipped; ingestion continues.

## Edges and provenance

| Edge | Provenance | Rule |
|---|---|---|
| `CONTAINS` | observed (`python-ast`) | Structural nesting only. |
| `IMPORTS` | observed (`import-resolution`) | Only in-repo resolvable modules. |
| `CALLS` | observed (`name-resolution`) or inferred (`name-heuristic`) | See below. |
| `COVERED_BY` | inferred (`test-name-convention`, confidence `heuristic`) | Import + name-mention. |
| `MODIFIED_IN` | observed (`git-log`) | `File → Commit` only. |
| `AUTHORED_BY` | observed (`git-log`) | `Commit → Person`. |
| `OWNED_BY` | inferred (`git-history-ownership-heuristic`) | Authorship share with `weight`. |

### `CALLS` resolution rules

A call resolves to an **observed** edge only when the target is uniquely
determined without guessing:

- a call by simple name to a function defined in the same module;
- `self.<method>` / `cls.<method>` to a method of the enclosing class;
- `<alias>.<function>` where `<alias>` is an `import`/`from ... import` alias;
- a bare name bound by `from <module> import <function>`.

A call resolves to an **inferred** edge (confidence `heuristic`) only when the
simple name is unique **repo-wide**. Ambiguous names and dynamic/attribute calls
whose owner cannot be resolved produce **no edge** (never guessed). External
calls (e.g. `os.environ.get`) produce no edge; the declaration still appears in
the importing File's `imports_declared`.

### `COVERED_BY` heuristic

A `Test` covers a `Function` when the test file's text both references the
function's module and mentions the function's simple name. This is a name-based
approximation, not a coverage measurement; it is always `inferred`
(confidence `heuristic`) and is superseded by any real coverage-run source if
one is added later (`provenance_policy.observed_when` in C1).

### History

- Git history is bounded by `max_commits` (default 500).
- `MODIFIED_IN` is `File → Commit`; `Function → Commit` requires hunk-line
  mapping and is not emitted yet.
- When the tree is not a git repository (or git is unavailable),
  `history_available` is `false` and no `Commit`/`Person` nodes are emitted.
- A non-git tree requires an explicit `revision` (40-char SHA); otherwise
  `IngestionError` is raised so no entity is emitted without a revision stamp.

## Contract subtyping note

C1 lists `CALLS.from = ["Function"]`, and its `Test` definition states "A Test
is a Function subclass by detection convention". The schema validator
(`tracefix/graph/schema.py`) therefore lets a `Test` node satisfy a `Function`
endpoint constraint. This interpretation is recorded here because it is a
code-level clarification of an approved contract; the contract file itself is
unchanged.

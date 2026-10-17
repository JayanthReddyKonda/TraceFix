# Experiment report template (controlled study)

> Copy this file to `docs/experiments/<date>-<slug>.md` and fill it in.
>
> **This is a controlled study, not a validated benchmark.** Single-arm or
> small-sample results must not be described as benchmark performance, and no
> retrieval or repair *improvement* may be claimed without a same-fingerprint
> comparison and the decisions below being finalized by Workstream B.

## Summary

- One-paragraph description of what was run and what was observed.
- Explicitly state: **controlled study; ground truth provisional; no
  improvement claim.**

## Configuration (reproducible)

| Field | Value |
|---|---|
| Case-set fingerprint | `<sha256>` |
| Fingerprint excludes excluded cases | `yes` (current behavior; Q-B10 open) |
| Evaluation contract version | `0.1.0-draft` (unfinalized) |
| Strategy name | `<name>` |
| Strategy config | `<serialized>` |
| Metric config (k values, primary k) | `<...>` (provisional, Q-B8) |
| Exact command | `<command>` |
| Source revisions | `<repo @ sha>` |

## Dataset provenance (mandatory)

- Dataset source: `<swe-bench | bugsinpy | ...>`
- Raw-rows provenance: `<URL / dataset revision / checksum, or
  "UNVERIFIED">`
- License: `<...>`
- Ground-truth policy: `<...>` — **provisional** (Q-B7 unresolved)
- Contamination: `<pre_cutoff>/<total>` cases are pre-model-cutoff; results may
  overstate generalization to post-cutoff bugs.

## Denominators (mandatory)

| Metric | Numerator | Denominator | Value |
|---|---|---|---|
| Hit@k (macro) | | # evaluated localizable cases | |
| Recall@k (macro) | | # evaluated localizable cases (defined only) | |
| Recall@k (micro) | | # ground-truth functions | |
| Mean latency | | # evaluated cases | |
| Candidate tokens | | # cases with content available | |

Excluded cases and reasons:

| case_id | reason |
|---|---|
| | |

Undefined metric counts (never reported as zero): `<...>`

## Results

- Per-case table (or reference to the run record JSON).
- Aggregate table.
- Failures and partial results (retrieval errors are recorded, not scored).

## Interpretation and limitations

- What the numbers do and do not support.
- Known confounds: provisional ground truth, unverified raw-row provenance,
  pre-cutoff contamination, small sample, unresolved C4 choices.
- Next step and what must be decided first.

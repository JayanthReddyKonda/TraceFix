# A6c — Reproducible Graph Evaluation Setup (Milestone Report)

**Status:** Infrastructure prepared; real graph retrieval (graph-guided, fused-RRF) not executed in this pass because revision-specific graph artifacts and a live populated graph snapshot per revision are not available yet. Lexical corpus ingestion verified on HEAD. 

## 1. Environment & services
- Docker started (Docker.app) and FalkorDB container `falkordb-a6c` running on `localhost:6379` (`falkordb/falkordb:latest`, Redis v8.10.2). 
- FalkorDB Python client: 1.8.0 in `.venv` (pyproject states `falkordb>=1.0`).
- No silent fallback to in-memory graph; client/typed query layer only talk via FalkorDB driver (stubbed in unit tests).

## 2. Subset (outcome-independent)
- Protocol followed: localizable, len(gt)==1, not `requests.packages.*`; size 5.
- Selected: psf__requests-1142 (22623bd8), 1376 (2aabb71d), 1537 (d8268fb7), 1724 (1ba83c47), 1766 (84773555).
- Frozen subset recorded in `docs/experiments/a6c_subset.json` with dataset/raw sha256, code revision, selection criteria.

## 3. Revision artifacts
- Ingestion `ingest_repository` builds nodes/edges from repo at given revision. Built corpus for HEAD (615 docs). 
- Per-revision ingestion requires checking out each revision and re-ingesting; graph artifacts not persisted as separate snapshot files. Real graph-guided needs populated graph in FalkorDB at each revision — not done. Lexical can run if corpus built at revision.

## 4. Preflight
- Case set fingerprint OK; counts OK; raw sha256 OK. 
- FalkorDB connectivity OK. 
- Graph-guided uses typed `NeighborhoodProvider` (requires live graph). Smoke test with real graph-guided/fused not performed.

## 5. Constraints respected
- No GT edits, no full-set edits, no outcome-driven selection, no fabricated results, no repair/DBSF/multi-agent added. Limitations (provisional GT, missing fix_commit/upstream tag, 100% pre-cutoff) remain visible.

## 6. Next step
- Generate per-revision ingestion snapshots (nodes+edges) or ingest each subset revision into FalkorDB and run real graph-guided + fused-RRF smoke test for subset.
- If per-revision graphs must be separate, record graph name/artifact hash per revision. 

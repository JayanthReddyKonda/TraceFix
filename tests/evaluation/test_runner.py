"""Single-arm runner tests (A6a): honesty, denominators, reproducibility."""

from __future__ import annotations

import json
from pathlib import Path

from tracefix.evaluation.cases import CaseRecord, CaseSet, load_case_set
from tracefix.evaluation.metrics import MetricsConfig
from tracefix.evaluation.runner import EvaluationRunner, evaluate_case_set
from tracefix.graph.models import Provenance
from tracefix.retrieval.interfaces import (
    EvidenceTarget,
    PartialReason,
    RankedItem,
    RetrievalError,
    RetrievalQuery,
    RetrievalResult,
)

POOL = Path(__file__).resolve().parents[2] / "eval" / "cases" / "requests_swe_bench_candidates.json"
R1, R2 = "1" * 40, "2" * 40


def _item(eid: str, rank: int, symbol: str | None, revision: str) -> RankedItem:
    return RankedItem(
        evidence_id=eid,
        strategy="stub",
        rank=rank,
        score=1.0 / rank,
        target=EvidenceTarget(file="m.py", symbol=symbol, lines=(1, 2)),
        source_revision=revision,
        provenance=Provenance.OBSERVED,
        source="stub",
    )


class StubStrategy:
    def __init__(
        self,
        items_by_case: dict[str, list[RankedItem]],
        *,
        name: str = "stub",
        fail: bool = False,
        partial: bool = False,
        elapsed_ms: float = 1.0,
    ) -> None:
        self.name = name
        self._items = items_by_case
        self._fail = fail
        self._partial = partial
        self._elapsed = elapsed_ms

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        if self._fail:
            raise RetrievalError("stub failure")
        items = self._items.get(query.case_id, [])
        return RetrievalResult(
            items=items,
            complete=not self._partial,
            partial_reason=PartialReason.LIMIT_REACHED if self._partial else None,
            strategy=self.name,
            revision=query.revision,
            elapsed_ms=self._elapsed,
        )


def _case(case_id: str, revision: str, gt: list[str]) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        repo="https://github.com/psf/requests",
        revision=revision,
        bug_report=f"report {case_id}",
        ground_truth_files=["m.py"],
        ground_truth_functions=gt,
        localizable=True,
    )


def _excluded(case_id: str) -> CaseRecord:
    return CaseRecord(
        case_id=case_id,
        repo="https://github.com/psf/requests",
        revision=R1,
        bug_report="report",
        localizable=False,
        excluded_reason="no-enclosing-function",
    )


def _case_set() -> CaseSet:
    return CaseSet(
        contract_version="0.1.0-draft",
        repo="https://github.com/psf/requests",
        dataset_source="swe-bench",
        license="Apache-2.0",
        ground_truth_status="provisional (pending Q-B7)",
        cases=[_case("c1", R1, ["m.f"]), _case("c2", R2, ["m.g"]), _excluded("c3")],
    )


def _relevance(case: CaseRecord, item: RankedItem) -> bool:
    symbol = item.target.symbol
    return symbol is not None and symbol in set(case.ground_truth_functions)


def _runner(strategy: StubStrategy, **kw: object) -> EvaluationRunner:
    return EvaluationRunner(
        strategy,
        command="pytest stub",
        relevance=_relevance,
        **kw,
    )


def test_ok_case_computes_ranks_and_denominators() -> None:
    strategy = StubStrategy({"c1": [_item("e1", 1, "x", R1), _item("e2", 2, "m.f", R1)]})
    report = evaluate_case_set(strategy, _case_set(), command="pytest", relevance=_relevance)
    c1 = next(c for c in report.cases if c.case_id == "c1")
    assert c1.status == "ok" and c1.evaluated is True
    assert c1.relevant_ranks == [2]
    assert c1.first_relevant_rank == 2
    assert c1.hit_at_k["5"] is True
    assert c1.recall_at_k["5"] == 1.0
    assert report.aggregate.cases_evaluated == 2
    assert report.aggregate.cases_excluded == 1
    assert report.aggregate.hit_at_k_denominator["10"] == 2


def test_excluded_case_is_omitted_from_denominators() -> None:
    strategy = StubStrategy({})
    report = evaluate_case_set(strategy, _case_set(), command="pytest", relevance=_relevance)
    c3 = next(c for c in report.cases if c.case_id == "c3")
    assert c3.status == "excluded" and c3.evaluated is False
    assert c3.note == "no-enclosing-function"
    assert report.excluded == [{"case_id": "c3", "reason": "no-enclosing-function"}]
    assert report.aggregate.cases_evaluated == 2  # c3 not counted


def test_failure_is_not_a_zero_rank_success() -> None:
    strategy = StubStrategy({}, fail=True)
    report = evaluate_case_set(strategy, _case_set(), command="pytest", relevance=_relevance)
    failed = [c for c in report.cases if c.status == "failed"]
    assert len(failed) == 2
    assert all(c.evaluated is False for c in failed)
    assert all(c.failure and "RetrievalError" in c.failure for c in failed)
    assert report.aggregate.cases_evaluated == 0
    assert report.aggregate.cases_failed == 2
    # undefined, not a misleading successful zero
    assert report.aggregate.hit_at_k_macro["10"] is None


def test_partial_result_recorded_as_note() -> None:
    strategy = StubStrategy({"c1": [_item("e1", 1, "m.f", R1)]}, partial=True)
    report = evaluate_case_set(strategy, _case_set(), command="pytest", relevance=_relevance)
    c1 = next(c for c in report.cases if c.case_id == "c1")
    assert c1.status == "ok"
    assert c1.note == "partial: limit_reached"


def test_duplicate_evidence_ids_counted() -> None:
    strategy = StubStrategy({"c1": [_item("dup", 1, "m.f", R1), _item("dup", 2, "x", R1)]})
    report = evaluate_case_set(strategy, _case_set(), command="pytest", relevance=_relevance)
    c1 = next(c for c in report.cases if c.case_id == "c1")
    assert c1.duplicates == 1
    assert report.aggregate.total_duplicates == 1


def test_reproducible_fields_stable_and_volatile_separate() -> None:
    first = _runner(StubStrategy({"c1": [_item("e1", 1, "m.f", R1)]})).run(_case_set())
    second = _runner(StubStrategy({"c1": [_item("e1", 1, "m.f", R1)]})).run(_case_set())
    assert first.reproducible_dict() == second.reproducible_dict()
    assert first.generated_at is not None  # volatile, present in the full record
    assert first.environment["python_version"]


def test_volatile_fields_excluded_from_reproducible_json() -> None:
    strategy = StubStrategy({})
    report = evaluate_case_set(strategy, _case_set(), command="pytest", relevance=_relevance)
    stable = json.loads(report.to_json(include_volatile=False))
    assert "generated_at" not in stable
    assert "environment" not in stable
    assert "case_set_fingerprint" in stable


def test_provisional_and_provenance_flags_surfaced() -> None:
    case_set = _case_set()
    strategy = StubStrategy({})
    report = evaluate_case_set(strategy, case_set, command="pytest", relevance=_relevance)
    assert report.dataset["ground_truth_is_provisional"] is True
    assert report.dataset["provenance_verified"] is False
    assert report.fingerprint_includes_excluded is False


def test_candidate_tokens_optional() -> None:
    class Counter:
        def count(self, text: str) -> int:
            return len(text)

    strategy = StubStrategy({"c1": [_item("e1", 1, "m.f", R1)]})
    report = evaluate_case_set(
        strategy,
        _case_set(),
        command="pytest",
        relevance=_relevance,
        token_counter=Counter(),
        content_resolver=lambda item: "xxxx",
    )
    c1 = next(c for c in report.cases if c.case_id == "c1")
    assert c1.candidate_tokens == 4
    assert report.aggregate.total_candidate_tokens == 4


def test_runner_over_frozen_pool_is_read_only_and_signals_provisional() -> None:
    case_set = load_case_set(POOL)
    before = POOL.read_text(encoding="utf-8")
    strategy = StubStrategy({})  # returns nothing; no Docker/FalkorDB/network
    report = evaluate_case_set(
        strategy, case_set, command="pytest stub", metrics=MetricsConfig(k_values=(5, 10, 20))
    )
    assert report.aggregate.cases_evaluated == 43
    assert report.aggregate.cases_excluded == 1
    assert report.aggregate.cases_failed == 0
    assert report.contamination["pre_cutoff_cases"] == 44
    assert report.case_set_fingerprint == case_set.fingerprint()
    assert POOL.read_text(encoding="utf-8") == before  # unchanged


def test_reproducible_json_is_stable_across_runs() -> None:
    def run() -> str:
        strategy = StubStrategy({"c1": [_item("e1", 1, "m.f", R1)]}, elapsed_ms=2.0)
        return _runner(strategy).run(_case_set()).to_json(include_volatile=False)

    assert run() == run()
    json.loads(run())  # valid JSON

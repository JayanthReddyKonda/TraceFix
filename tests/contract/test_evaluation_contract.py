"""Contract tests for evaluation artifacts (A6a, service-free).

These lock the *documented* fingerprints and reproducibility rules in
`contracts/evaluation.json` (C4 draft). They do not finalize C4 and do not
claim the provisional metric defaults are approved.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tracefix.evaluation.cases import CaseRecord, CaseSet, load_case_set
from tracefix.evaluation.metrics import MetricsConfig
from tracefix.evaluation.runner import evaluate_case_set
from tracefix.retrieval.interfaces import RetrievalQuery, RetrievalResult

POOL = Path(__file__).resolve().parents[2] / "eval" / "cases" / "requests_swe_bench_candidates.json"


@pytest.mark.contract
def test_case_set_fingerprint_matches_contract_formula() -> None:
    raw = json.loads(POOL.read_text(encoding="utf-8"))
    contract_version = raw["evaluation_contract_version"]
    pairs = sorted((c["case_id"], c["revision"]) for c in raw["cases"] if c["localizable"])
    payload = json.dumps([pairs, contract_version], separators=(",", ":"))
    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    assert expected == raw["case_set_fingerprint"]
    assert load_case_set(POOL).fingerprint() == expected


class _Strategy:
    name = "stub"

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        return RetrievalResult(
            items=[],
            complete=True,
            strategy=self.name,
            revision=query.revision,
            elapsed_ms=0.0,
        )


def _tiny_case_set() -> CaseSet:
    return CaseSet(
        contract_version="0.1.0-draft",
        repo="https://github.com/psf/requests",
        dataset_source="swe-bench",
        license="Apache-2.0",
        ground_truth_status="provisional (pending Q-B7)",
        cases=[
            CaseRecord(
                case_id="c1",
                repo="https://github.com/psf/requests",
                revision="a" * 40,
                bug_report="b",
                ground_truth_files=["m.py"],
                ground_truth_functions=["m.f"],
                localizable=True,
            )
        ],
    )


@pytest.mark.contract
def test_runner_reproducible_record_carries_mandatory_reporting_fields() -> None:
    report = evaluate_case_set(
        _Strategy(),
        _tiny_case_set(),
        command="pytest -m contract",
        metrics=MetricsConfig(k_values=(5, 10, 20)),
    )
    stable = report.reproducible_dict()
    for key in (
        "case_set_fingerprint",
        "evaluation_contract_version",
        "strategy_name",
        "strategy_config",
        "metric_config",
        "command",
        "dataset",
        "contamination",
        "denominators",
        "excluded",
        "aggregate",
    ):
        assert key in stable, f"missing mandatory reporting field: {key}"
    # volatile metadata must not leak into the reproducible record
    assert "generated_at" not in stable
    assert "environment" not in stable
    # provenance and provisional ground truth are stated honestly
    assert stable["dataset"]["ground_truth_is_provisional"] is True
    assert stable["dataset"]["provenance_verified"] is False
    assert "pre_cutoff_cases" in stable["contamination"]
    assert "cases_evaluated" in stable["denominators"]


@pytest.mark.contract
def test_runner_report_round_trips_through_json() -> None:
    report = evaluate_case_set(_Strategy(), _tiny_case_set(), command="pytest -m contract")
    stable = report.reproducible_dict()
    restored = json.loads(report.to_json(include_volatile=False))
    assert restored == stable
    assert restored["case_set_fingerprint"] == report.case_set_fingerprint

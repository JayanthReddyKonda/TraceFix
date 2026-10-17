"""Case-set model, loader, and fingerprint tests (A6a)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracefix.evaluation.cases import (
    CaseRecord,
    CaseSet,
    EvaluationError,
    fingerprint_cases,
    load_case_set,
)

POOL = Path(__file__).resolve().parents[2] / "eval" / "cases" / "requests_swe_bench_candidates.json"
RECORDED_FINGERPRINT = "da1c89d31006ac65753d31fcb719b457ce5cb000e14e0735126018a90e350858"


def _record(case_id: str = "c1", *, localizable: bool = True, **kw: object) -> dict:
    base: dict = {
        "case_id": case_id,
        "repo": "https://github.com/psf/requests",
        "revision": "a" * 40,
        "bug_report": "boom",
        "ground_truth_files": ["requests/x.py"],
        "ground_truth_functions": ["requests.x.f"],
        "localizable": localizable,
        "excluded_reason": None if localizable else "no-enclosing-function",
    }
    base.update(kw)
    return base


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_existing_requests_pool() -> None:
    case_set = load_case_set(POOL)
    assert case_set.contract_version == "0.1.0-draft"
    assert case_set.repo == "https://github.com/psf/requests"
    assert len(case_set.cases) == 44
    assert len(case_set.localizable) == 43
    assert len(case_set.excluded) == 1
    assert case_set.excluded[0].case_id == "psf__requests-4106"
    assert case_set.ground_truth_is_provisional is True


def test_existing_pool_fingerprint_reproduces_recorded() -> None:
    case_set = load_case_set(POOL)
    assert case_set.fingerprint() == RECORDED_FINGERPRINT
    assert case_set.fingerprint_matches_recorded() is True


def test_fingerprint_is_deterministic_and_order_independent() -> None:
    a = CaseRecord(**_record("a", revision="1" * 40))
    b = CaseRecord(**_record("b", revision="2" * 40))
    forward = fingerprint_cases([a, b], "0.1.0-draft")
    reverse = fingerprint_cases([b, a], "0.1.0-draft")
    assert forward == reverse
    assert forward == fingerprint_cases([a, b], "0.1.0-draft")


def test_fingerprint_treatment_of_excluded_cases() -> None:
    included = CaseRecord(**_record("inc"))
    excluded = CaseRecord(**_record("exc", localizable=False))
    case_set = CaseSet(
        contract_version="0.1.0-draft",
        cases=[included, excluded],
    )
    assert case_set.fingerprint() == fingerprint_cases([included], "0.1.0-draft")
    assert case_set.fingerprint(include_excluded=True) == fingerprint_cases(
        [included, excluded], "0.1.0-draft"
    )
    assert case_set.fingerprint() != case_set.fingerprint(include_excluded=True)


def test_duplicate_case_ids_rejected(tmp_path: Path) -> None:
    payload = {
        "evaluation_contract_version": "0.1.0-draft",
        "cases": [_record("dup"), _record("dup")],
    }
    with pytest.raises(EvaluationError, match="duplicate case_id"):
        load_case_set(_write(tmp_path, payload))


def test_missing_required_field_rejected(tmp_path: Path) -> None:
    bad = _record("c1")
    del bad["revision"]
    payload = {"evaluation_contract_version": "0.1.0-draft", "cases": [bad]}
    with pytest.raises(EvaluationError):
        load_case_set(_write(tmp_path, payload))


def test_localizable_without_ground_truth_rejected(tmp_path: Path) -> None:
    bad = _record("c1", ground_truth_functions=[])
    payload = {"evaluation_contract_version": "0.1.0-draft", "cases": [bad]}
    with pytest.raises(EvaluationError):
        load_case_set(_write(tmp_path, payload))


def test_excluded_without_reason_rejected(tmp_path: Path) -> None:
    bad = _record("c1", localizable=False, excluded_reason=None)
    payload = {"evaluation_contract_version": "0.1.0-draft", "cases": [bad]}
    with pytest.raises(EvaluationError):
        load_case_set(_write(tmp_path, payload))


def test_invalid_json_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(EvaluationError, match="invalid JSON"):
        load_case_set(path)


def test_non_object_json_rejected(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(EvaluationError, match="must be a JSON object"):
        load_case_set(path)


def test_missing_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(EvaluationError, match="not found"):
        load_case_set(tmp_path / "absent.json")

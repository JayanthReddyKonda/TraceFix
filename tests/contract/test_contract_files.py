"""Contract-file integrity tests (Checkpoint 0, service-free).

These tests lock the Checkpoint 0 contract states and the amendments the
integration owner required. Changing a contract status is a deliberate act:
update the contract and this test together via the contract-change procedure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
CONTRACT_FILES = (
    "graph_schema.json",
    "retrieval.json",
    "context_manifest.json",
    "evaluation.json",
)
DRAFT_FILES = ("context_manifest.json", "evaluation.json")
APPROVED_FILES = ("graph_schema.json", "retrieval.json")
SEMVER = re.compile(r"^\d+\.\d+\.\d+")
ALLOWED_STATUS = {"approved-in-principle", "draft-pending-workstream-b-review"}


def _load(name: str) -> dict:
    path = CONTRACTS_DIR / name
    assert path.is_file(), f"missing contract file: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.contract
@pytest.mark.parametrize("name", CONTRACT_FILES)
def test_contract_file_parses_with_required_fields(name: str) -> None:
    data = _load(name)
    assert data["contract"].startswith("tracefix.")
    assert SEMVER.match(data["version"]), data["version"]
    assert data["status"] in ALLOWED_STATUS, data["status"]
    assert data["checkpoint"] == "0-D1"


@pytest.mark.contract
def test_status_vocabulary_is_exactly_the_checkpoint_zero_states() -> None:
    statuses = {_load(name)["status"] for name in CONTRACT_FILES}
    assert statuses == ALLOWED_STATUS


@pytest.mark.contract
@pytest.mark.parametrize("name", DRAFT_FILES)
def test_draft_contracts_carry_open_questions_for_workstream_b(name: str) -> None:
    data = _load(name)
    assert data["status"] == "draft-pending-workstream-b-review"
    questions = data["open_questions_for_workstream_b"]
    assert isinstance(questions, list) and questions, "drafts must list open questions for B"
    assert all(q.startswith("Q-B") for q in questions)


@pytest.mark.contract
def test_graph_schema_declares_provenance_and_identity_amendments() -> None:
    data = _load("graph_schema.json")
    provenance = data["provenance"]
    assert set(provenance["values"]) == {"observed", "inferred"}
    identity = data["identity"]
    assert identity["revision_property"] == "revision"
    assert identity["content_hash_property"] == "content_hash"
    assert "revision-independent" in identity["entity_id"]


@pytest.mark.contract
def test_retrieval_declares_provenance_revision_and_failure_semantics() -> None:
    data = _load("retrieval.json")
    item = data["ranked_item"]
    assert item["provenance"] == "observed | inferred (semantics per contracts/graph_schema.json)"
    assert "source_revision" in item
    result = data["retrieval_result"]
    for field in ("complete", "partial_reason", "failure"):
        assert field in result
    assert "RetrievalError" in data["failure_semantics"]
    assert data["partial_reasons"], "partial results must have named reasons"

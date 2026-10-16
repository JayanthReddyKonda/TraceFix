"""Graph schema contract invariants (Checkpoint 0 D1 amendments).

Validates the C1 contract file itself. Instance-level validation against this
schema is Phase 1 (task A1.1/A1.2) and is intentionally not performed here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "graph_schema.json"
DEFERRED_EDGE_TYPES = {
    "AFFECTS",
    "RESOLVED_BY",
    "KNOWS",
    "INSTANCE_OF",
    "PROMOTED_TO",
    "SOURCE",
    "REQUIRES",
}
ACTIVE_EDGE_TYPES = {
    "CONTAINS",
    "IMPORTS",
    "CALLS",
    "COVERED_BY",
    "MODIFIED_IN",
    "AUTHORED_BY",
    "OWNED_BY",
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _kinds(groups: list) -> set[str]:
    kinds: set[str] = set()
    for group in groups:
        if isinstance(group, list):
            kinds.update(group)
        else:
            kinds.add(group)
    return kinds


@pytest.mark.contract
def test_active_layers_are_code_and_history_only() -> None:
    scope = _schema()["scope"]
    assert scope["layers_active"] == ["code", "history"]
    for layer in ("knowledge", "decision", "incident", "procedural", "agent_state"):
        assert layer in scope["layers_deferred"]


@pytest.mark.contract
def test_node_types_match_approved_scope() -> None:
    nodes = _schema()["node_types"]
    by_layer: dict[str, set[str]] = {}
    for name, spec in nodes.items():
        by_layer.setdefault(spec["layer"], set()).add(name)
    assert by_layer["code"] == {"Repository", "File", "Module", "Class", "Function", "Test"}
    assert by_layer["history"] == {"Commit", "Person"}


@pytest.mark.contract
def test_edges_reference_declared_node_kinds_only() -> None:
    schema = _schema()
    declared = set(schema["node_types"])
    for name, spec in schema["edge_types"].items():
        from_kinds = _kinds(spec["from"])
        to_kinds = _kinds(spec["to"])
        assert from_kinds <= declared, f"{name} from-kinds undeclared: {from_kinds - declared}"
        assert to_kinds <= declared, f"{name} to-kinds undeclared: {to_kinds - declared}"


@pytest.mark.contract
def test_no_deferred_edge_types_are_active() -> None:
    active = set(_schema()["edge_types"])
    overlap = active & DEFERRED_EDGE_TYPES
    assert not overlap, f"deferred edges active: {overlap}"
    assert active == ACTIVE_EDGE_TYPES


@pytest.mark.contract
def test_every_edge_declares_provenance_policy_with_both_values() -> None:
    for name, spec in _schema()["edge_types"].items():
        policy = spec["provenance_policy"]
        assert policy["default"] in {"observed", "inferred"}, name
        assert policy["sources"], f"{name} must name its source artifacts"


@pytest.mark.contract
def test_identity_rules_separate_revision_and_content_hash_from_entity_id() -> None:
    identity = _schema()["identity"]
    assert identity["revision_property"] == "revision"
    assert identity["content_hash_property"] == "content_hash"
    assert "must not mint a new entity_id" in identity["rule"]

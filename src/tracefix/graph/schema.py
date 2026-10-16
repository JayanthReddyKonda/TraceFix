"""Validation of nodes/edges/snapshots against contracts/graph_schema.json (C1).

Instance-level validation (workstream task A1.1). The contract file is the
single source of truth for kinds, required properties, and edge endpoint rules;
this module loads it and enforces those rules without generating Cypher.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tracefix.graph.models import Edge, Node

DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "graph_schema.json"
_SHA = re.compile(r"^[0-9a-f]{40}$")
# Common node properties live on the Node model itself, not in `properties`.
_STRUCTURAL_FIELDS = frozenset({"entity_id", "kind", "repo", "revision"})
# The contract states Test is "a Function subclass by detection convention".
# Endpoint-kind checks therefore let a Test satisfy a Function constraint.
_FUNCTION_LIKE = {"Test": {"Test", "Function"}}


def _satisfies(actual: str, allowed: set[str]) -> bool:
    return bool(({actual} | _FUNCTION_LIKE.get(actual, set())) & allowed)


class SchemaValidationError(Exception):
    """A node/edge/snapshot violates the C1 contract."""


def _kinds(groups: list[Any]) -> set[str]:
    kinds: set[str] = set()
    for group in groups:
        if isinstance(group, list):
            kinds.update(group)
        else:
            kinds.add(group)
    return kinds


class GraphSchema:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.node_types: dict[str, dict[str, Any]] = data["node_types"]
        self.edge_types: dict[str, dict[str, Any]] = data["edge_types"]
        self._edge_from: dict[str, set[str]] = {
            name: _kinds(spec["from"]) for name, spec in self.edge_types.items()
        }
        self._edge_to: dict[str, set[str]] = {
            name: _kinds(spec["to"]) for name, spec in self.edge_types.items()
        }

    @classmethod
    def load(cls, path: Path | None = None) -> GraphSchema:
        contract_path = path or DEFAULT_CONTRACT_PATH
        return cls(json.loads(contract_path.read_text(encoding="utf-8")))

    def validate_node(self, node: Node) -> None:
        spec = self.node_types.get(node.kind)
        if spec is None:
            raise SchemaValidationError(f"undeclared node kind: {node.kind!r}")
        if not _SHA.match(node.revision):
            raise SchemaValidationError(f"node {node.entity_id}: revision is not a full SHA")
        required = [p for p in spec.get("required_properties", []) if p not in _STRUCTURAL_FIELDS]
        missing = [p for p in required if p not in node.properties]
        if missing:
            raise SchemaValidationError(
                f"node {node.kind} {node.entity_id}: missing required properties {missing}"
            )

    def validate_edge(self, edge: Edge, known_ids: set[str] | None = None) -> None:
        spec = self.edge_types.get(edge.edge_type)
        if spec is None:
            raise SchemaValidationError(f"undeclared edge type: {edge.edge_type!r}")
        if edge.source_id not in self._edge_from[edge.edge_type]:
            # source/target are entity ids; endpoint *kinds* are checked when the
            # caller supplies an id->kind map via validate_snapshot.
            pass
        if not _SHA.match(edge.revision):
            raise SchemaValidationError(f"edge {edge.edge_type}: revision is not a full SHA")
        if known_ids is not None:
            for endpoint in (edge.source_id, edge.target_id):
                if endpoint not in known_ids:
                    raise SchemaValidationError(
                        f"edge {edge.edge_type}: endpoint {endpoint!r} not present in snapshot"
                    )

    def validate_snapshot(self, nodes: list[Node], edges: list[Edge]) -> None:
        """Validate a full snapshot: node kinds/props, edge endpoints and kinds."""
        by_id: dict[str, Node] = {}
        for node in nodes:
            if node.entity_id in by_id:
                raise SchemaValidationError(f"duplicate entity_id: {node.entity_id}")
            self.validate_node(node)
            by_id[node.entity_id] = node

        seen_edges: set[tuple[str, str, str, str]] = set()
        for edge in edges:
            self.validate_edge(edge, known_ids=set(by_id))
            src = by_id.get(edge.source_id)
            tgt = by_id.get(edge.target_id)
            if src is None or tgt is None:
                raise SchemaValidationError(
                    f"edge {edge.edge_type}: dangling endpoint "
                    f"{edge.source_id if src is None else edge.target_id}"
                )
            allowed_from = self._edge_from[edge.edge_type]
            allowed_to = self._edge_to[edge.edge_type]
            if not _satisfies(src.kind, allowed_from):
                raise SchemaValidationError(
                    f"edge {edge.edge_type}: source kind {src.kind!r} not allowed "
                    f"(allowed: {sorted(allowed_from)})"
                )
            if not _satisfies(tgt.kind, allowed_to):
                raise SchemaValidationError(
                    f"edge {edge.edge_type}: target kind {tgt.kind!r} not allowed "
                    f"(allowed: {sorted(allowed_to)})"
                )
            key = edge.identity()
            if key in seen_edges:
                raise SchemaValidationError(f"duplicate edge: {key}")
            seen_edges.add(key)

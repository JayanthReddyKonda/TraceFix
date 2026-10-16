"""Graph node/edge models implementing contracts/graph_schema.json (C1)."""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class Provenance(StrEnum):
    """Whether a relationship was read from an artifact or produced by a heuristic."""

    OBSERVED = "observed"
    INFERRED = "inferred"


class Node(BaseModel):
    """A graph entity. Kind-specific fields live in `properties` and are
    validated against the C1 contract by tracefix.graph.schema."""

    entity_id: str
    kind: str
    repo: str
    revision: str
    properties: dict[str, Any] = Field(default_factory=dict)
    content_hash: str | None = None
    ingested_at: str

    @model_validator(mode="after")
    def _check_revision(self) -> Node:
        if not GIT_SHA_RE.match(self.revision):
            raise ValueError(f"revision must be a full 40-char git SHA, got {self.revision!r}")
        return self


class Edge(BaseModel):
    """A relationship. Inferred edges must carry confidence (C1 provenance rule)."""

    edge_type: str
    source_id: str
    target_id: str
    provenance: Provenance
    source: str
    revision: str
    confidence: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_rules(self) -> Edge:
        if not GIT_SHA_RE.match(self.revision):
            raise ValueError(f"revision must be a full 40-char git SHA, got {self.revision!r}")
        if self.provenance is Provenance.INFERRED and not self.confidence:
            raise ValueError("inferred edges must declare confidence")
        return self

    def identity(self) -> tuple[str, str, str, str]:
        """Deduplication key: type + endpoints + source."""
        return (self.edge_type, self.source_id, self.target_id, self.source)


def normalize_repo_url(url: str) -> str:
    """Canonical repo URL form used in entity ids and the `repo` property."""
    cleaned = url.strip().removesuffix(".git").rstrip("/")
    if cleaned.startswith("git@github.com:"):
        cleaned = "https://github.com/" + cleaned.removeprefix("git@github.com:")
    return cleaned.lower()


def make_entity_id(repo_url: str, kind: str, qualified_key: str) -> str:
    """Revision-independent canonical entity id: <repo_url>#<kind>:<qualified_key>."""
    return f"{normalize_repo_url(repo_url)}#{kind}:{qualified_key}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

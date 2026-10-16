"""Retrieval strategy interfaces implementing contracts/retrieval.json (C2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from tracefix.graph.models import Provenance


class RetrievalError(Exception):
    """A strategy could produce no usable items (C2 failure semantics)."""


class PartialReason(StrEnum):
    LIMIT_REACHED = "limit_reached"
    TIMEOUT = "timeout"
    INDEX_INCOMPLETE = "index_incomplete"
    GRAPH_UNAVAILABLE = "graph_unavailable"
    STRATEGY_ERROR_RECOVERED = "strategy_error_recovered"


class RetrievalLimits(BaseModel):
    max_items: int = Field(gt=0)
    max_hops: int = Field(default=0, ge=0)
    timeout_ms: int = Field(gt=0)


class EvidenceTarget(BaseModel):
    file: str
    symbol: str | None = None
    lines: tuple[int, int] | None = None


class RankedItem(BaseModel):
    evidence_id: str
    strategy: str
    rank: int = Field(ge=1)
    score: float
    target: EvidenceTarget
    source_revision: str
    provenance: Provenance
    source: str


class Failure(BaseModel):
    error_type: str
    detail: str


class RetrievalQuery(BaseModel):
    case_id: str
    text: str
    revision: str
    k: int = Field(gt=0)
    limits: RetrievalLimits


class RetrievalResult(BaseModel):
    items: list[RankedItem] = Field(default_factory=list)
    complete: bool = True
    partial_reason: PartialReason | None = None
    failure: Failure | None = None
    strategy: str
    config: dict[str, Any] = Field(default_factory=dict)
    revision: str
    elapsed_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _check_semantics(self) -> RetrievalResult:
        if self.failure is not None and self.items:
            raise ValueError("a failed result must not carry items (C2 failure semantics)")
        if self.complete and self.partial_reason is not None:
            raise ValueError("complete results must not declare partial_reason")
        if not self.complete and self.partial_reason is None:
            raise ValueError("incomplete results must declare partial_reason")
        ranks = [item.rank for item in self.items]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(f"ranks must be dense and 1-based, got {ranks}")
        return self


@runtime_checkable
class RetrievalStrategy(Protocol):
    name: str

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...

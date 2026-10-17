"""Retrieval pipeline (A3.6): lexical + graph-guided + optional dense via RRF.

`RetrievalPipeline` runs a set of C2 `RetrievalStrategy` arms on one query,
filters revision-mismatched items, fuses the surviving rankings with Reciprocal
Rank Fusion, deduplicates by `evidence_id`, and returns a single
`RetrievalResult` that still satisfies the C2 contract.

Properties enforced here:

- **Revision compatibility** — every item whose `source_revision` differs from
  the query revision is dropped (and counted), so nothing from another snapshot
  leaks into the package.
- **Determinism** — arms run in the configured order; fusion scores are
  order-insensitive and tie-break by ascending `evidence_id`; output ranks are
  dense and 1-based.
- **Dedup** — an `evidence_id` appears once; the first arm (in configured order)
  to produce it supplies the item's `provenance`/`source`/`target`; the fused
  RRF `score` and pipeline `strategy` name are applied.
- **Provenance preservation** — original `provenance` and `source` are retained.
- **Failure isolation** — an arm raising is recorded, not propagated; the
  pipeline `RetrievalError`s only when *every* arm fails.
- **Partial results** — an arm returning `complete=false` makes the pipeline
  result incomplete; the reported `partial_reason` follows a documented
  precedence. Over-cap truncation reports `limit_reached`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tracefix.graph.query import GraphPath
from tracefix.retrieval.fusion import DEFAULT_RRF_K, SUPPORTED_METHODS, fuse_ids
from tracefix.retrieval.interfaces import (
    PartialReason,
    RankedItem,
    RetrievalError,
    RetrievalQuery,
    RetrievalResult,
    RetrievalStrategy,
)

if TYPE_CHECKING:
    from tracefix.retrieval.context_selector import ContextCandidate

# Deterministic precedence when several arms degrade at once (worst first).
_PARTIAL_PRECEDENCE = (
    PartialReason.TIMEOUT,
    PartialReason.GRAPH_UNAVAILABLE,
    PartialReason.STRATEGY_ERROR_RECOVERED,
    PartialReason.INDEX_INCOMPLETE,
    PartialReason.LIMIT_REACHED,
)


@dataclass
class StrategyOutcome:
    name: str
    result: RetrievalResult | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.result is not None


class RetrievalPipeline:
    """Fuses several retrieval arms into one C2 result (implements the protocol)."""

    name = "fusion"

    def __init__(
        self,
        strategies: Sequence[RetrievalStrategy],
        *,
        method: str = "rrf",
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        if not strategies:
            raise ValueError("a pipeline needs at least one strategy")
        if method not in SUPPORTED_METHODS:
            raise ValueError(
                f"unknown fusion method {method!r}; supported: {sorted(SUPPORTED_METHODS)}"
            )
        self.strategies = list(strategies)
        self.method = method
        self.rrf_k = rrf_k

    def explain(self, evidence_id: str) -> GraphPath | None:
        """First non-null `explain()` from a contributing arm (e.g. graph path)."""
        for strategy in self.strategies:
            explain = getattr(strategy, "explain", None)
            if callable(explain):
                path: GraphPath | None = explain(evidence_id)
                if path is not None:
                    return path
        return None

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        outcomes = [self._run(strategy, query) for strategy in self.strategies]
        successful = [outcome for outcome in outcomes if outcome.ok]
        if not successful:
            raise RetrievalError(
                "all retrieval strategies failed: "
                + "; ".join(f"{o.name}: {o.error}" for o in outcomes)
            )

        by_id: dict[str, RankedItem] = {}
        rankings: list[list[str]] = []
        mismatches = 0
        total_items = 0
        for outcome in successful:
            assert outcome.result is not None
            kept_ids: list[str] = []
            for item in outcome.result.items:
                total_items += 1
                if item.source_revision != query.revision:
                    mismatches += 1
                    continue
                kept_ids.append(item.evidence_id)
                by_id.setdefault(item.evidence_id, item)
            rankings.append(kept_ids)

        fused = fuse_ids(rankings, method=self.method, k=self.rrf_k)
        max_items = query.limits.max_items
        truncated = len(fused) > max_items
        selected = fused[:max_items]

        items: list[RankedItem] = []
        for rank, (evidence_id, score) in enumerate(selected, start=1):
            base = by_id[evidence_id]
            items.append(
                base.model_copy(update={"rank": rank, "score": float(score), "strategy": self.name})
            )

        reasons = self._reasons(outcomes, truncated, mismatches)
        complete = not reasons
        config = {
            "strategy": self.name,
            "fusion": self.method,
            "rrf_k": self.rrf_k,
            "strategies": [outcome.name for outcome in successful],
            "outcomes": [
                {
                    "strategy": outcome.name,
                    "status": "ok" if outcome.ok else "error",
                    "error": outcome.error,
                    "item_count": len(outcome.result.items) if outcome.result else 0,
                    "complete": outcome.result.complete if outcome.result else False,
                    "partial_reason": (
                        outcome.result.partial_reason.value
                        if outcome.result and outcome.result.partial_reason
                        else None
                    ),
                }
                for outcome in outcomes
            ],
            "revision_mismatches": mismatches,
            "duplicates_removed": total_items - len(by_id),
        }
        result = RetrievalResult(
            items=items,
            complete=complete,
            partial_reason=None if complete else self._pick_reason(reasons),
            strategy=self.name,
            config=config,
            revision=query.revision,
            elapsed_ms=sum(
                outcome.result.elapsed_ms for outcome in successful if outcome.result is not None
            ),
        )
        return result

    @staticmethod
    def _run(strategy: RetrievalStrategy, query: RetrievalQuery) -> StrategyOutcome:
        try:
            return StrategyOutcome(name=strategy.name, result=strategy.retrieve(query))
        except Exception as exc:  # noqa: BLE001 - isolated per C2 failure semantics
            return StrategyOutcome(name=strategy.name, error=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _reasons(
        outcomes: list[StrategyOutcome], truncated: bool, mismatches: int
    ) -> list[PartialReason]:
        reasons: list[PartialReason] = []
        for outcome in outcomes:
            if outcome.result is None:
                reasons.append(PartialReason.STRATEGY_ERROR_RECOVERED)
            elif not outcome.result.complete and outcome.result.partial_reason is not None:
                reasons.append(outcome.result.partial_reason)
        if mismatches > 0:
            # An arm returned items from another revision: a contract violation.
            reasons.append(PartialReason.STRATEGY_ERROR_RECOVERED)
        if truncated:
            reasons.append(PartialReason.LIMIT_REACHED)
        return reasons

    @staticmethod
    def _pick_reason(reasons: list[PartialReason]) -> PartialReason:
        for candidate in _PARTIAL_PRECEDENCE:
            if candidate in reasons:
                return candidate
        return reasons[0]

    def to_candidates(
        self,
        result: RetrievalResult,
        content_resolver: Callable[[RankedItem], str],
        *,
        repo: str | None = None,
        evidence_type: str | None = None,
    ) -> list[ContextCandidate]:
        """Build context-selector candidates, attaching graph paths where known."""
        from tracefix.retrieval.context_selector import candidates_from_result

        return candidates_from_result(
            result,
            content_resolver,
            explain=self.explain,
            repo=repo,
            evidence_type=evidence_type,
        )

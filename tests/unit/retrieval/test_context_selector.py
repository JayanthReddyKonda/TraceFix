"""Context selector tests (A3.5): budget, duplicates, diversity, determinism."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tracefix.graph.ingestion import ingest_repository
from tracefix.graph.models import Provenance
from tracefix.graph.query import SnapshotNeighborhoodProvider
from tracefix.retrieval.context_selector import (
    CharDiv4TokenCounter,
    ContextBudget,
    ContextCandidate,
    ContextSelection,
    ContextSelector,
    ContextTotals,
    ExclusionReason,
    SelectionReason,
)
from tracefix.retrieval.graph_guided import GraphGuidedStrategy
from tracefix.retrieval.interfaces import (
    EvidenceTarget,
    RankedItem,
    RetrievalLimits,
    RetrievalQuery,
)
from tracefix.retrieval.lexical import LexicalBM25Strategy, build_function_corpus

REV = "a" * 40


def _tok(text: str) -> int:
    return (len(text) + 3) // 4


def make_item(
    eid: str,
    rank: int,
    *,
    file: str = "m.py",
    symbol: str | None = None,
    lines: tuple[int, int] | None = None,
    strategy: str = "graph_guided",
    source: str = "graph_seed",
    provenance: Provenance = Provenance.OBSERVED,
    revision: str = REV,
    score: float = 1.0,
) -> RankedItem:
    return RankedItem(
        evidence_id=eid,
        strategy=strategy,
        rank=rank,
        score=score,
        target=EvidenceTarget(file=file, symbol=symbol, lines=lines),
        source_revision=revision,
        provenance=provenance,
        source=source,
    )


def cand(eid: str, rank: int, content: str, **kw: Any) -> ContextCandidate:
    return ContextCandidate.from_item(make_item(eid, rank, **kw), content)


class ExactCharCounter:
    """Test double for an exact counter: one token per character."""

    name = "exact_chars"
    method = "fixed_per_char"
    encoding = "test"
    estimated = False

    def count(self, text: str) -> int:
        return len(text)

    def config(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "encoding": self.encoding,
            "method": self.method,
            "estimated": self.estimated,
        }


def test_empty_inputs() -> None:
    sel = ContextSelector(CharDiv4TokenCounter()).select([], token_limit=100)
    assert sel.items == [] and sel.excluded == []
    assert sel.totals.tokens == 0 and sel.totals.item_count == 0 and sel.totals.duplicates == 0
    assert sel.budget.token_limit == 100
    assert sel.budget.estimated is True
    assert sel.budget.tokenizer["method"] == "char_div_4"
    assert sel.budget.tokenizer["encoding"] is None


def test_exact_fit_selects_all() -> None:
    candidates = [cand("e1", 1, "aaaa"), cand("e2", 2, "bbbb")]
    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=2)
    assert [i.evidence_id for i in sel.items] == ["e1", "e2"]
    assert sel.totals.tokens == 2
    assert sel.excluded == []


def test_boundary_one_token_short_rejects() -> None:
    candidates = [cand("e1", 1, "aaaa"), cand("e2", 2, "bbbb")]
    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=1)
    assert [i.evidence_id for i in sel.items] == ["e1"]
    assert [e.evidence_id for e in sel.excluded] == ["e2"]
    assert sel.excluded[0].reason is ExclusionReason.OVER_BUDGET
    assert sel.totals.tokens == 1


def test_over_budget_item_is_skipped_and_later_item_fills() -> None:
    candidates = [
        cand("e1", 1, "a" * 8),  # 2 tokens
        cand("e2", 2, "b" * 8),  # 2 tokens
        cand("e3", 3, "c" * 4),  # 1 token
    ]
    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=3)
    assert [i.evidence_id for i in sel.items] == ["e1", "e3"]
    assert sel.totals.tokens == 3
    assert [e.reason for e in sel.excluded] == [ExclusionReason.OVER_BUDGET]


def test_item_larger_than_budget_is_too_large() -> None:
    candidates = [cand("e1", 1, "a" * 20)]
    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=3)
    assert sel.items == []
    assert sel.excluded[0].reason is ExclusionReason.ITEM_TOO_LARGE
    assert sel.totals.tokens == 0


def test_duplicate_evidence_id_selected_once() -> None:
    candidates = [cand("e1", 1, "aaaa"), cand("e1", 2, "bbbb")]
    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=10)
    assert [i.evidence_id for i in sel.items] == ["e1"]
    assert sel.totals.duplicates == 1
    assert sel.excluded[0].reason is ExclusionReason.DUPLICATE
    assert sel.excluded[0].token_contribution is None


def test_zero_length_content_costs_nothing() -> None:
    sel = ContextSelector(CharDiv4TokenCounter()).select([cand("e1", 1, "")], token_limit=1)
    assert [i.evidence_id for i in sel.items] == ["e1"]
    assert sel.items[0].token_contribution == 0


def test_file_diversity_cap_preserves_spread() -> None:
    candidates = [
        cand("a1", 1, "aaaa", file="a.py"),
        cand("a2", 2, "aaaa", file="a.py"),
        cand("a3", 3, "aaaa", file="a.py"),
        cand("b1", 4, "aaaa", file="b.py"),
    ]
    selector = ContextSelector(CharDiv4TokenCounter(), max_items_per_file=1)
    sel = selector.select(candidates, token_limit=4)
    assert [i.evidence_id for i in sel.items] == ["a1", "b1"]
    assert [i.selection_reason for i in sel.items] == [
        SelectionReason.DIVERSITY_SPREAD,
        SelectionReason.DIVERSITY_SPREAD,
    ]
    assert [e.evidence_id for e in sel.excluded] == ["a2", "a3"]
    assert all(e.reason is ExclusionReason.DIVERSITY_CAP for e in sel.excluded)
    assert sel.totals.tokens == 2  # under-filled because the cap binds


def test_source_diversity_cap() -> None:
    candidates = [
        cand("c1", 1, "aaaa", source="bm25"),
        cand("c2", 2, "aaaa", source="bm25"),
        cand("c3", 3, "aaaa", source="graph_callees"),
    ]
    selector = ContextSelector(CharDiv4TokenCounter(), max_items_per_source=1)
    sel = selector.select(candidates, token_limit=3)
    assert [i.evidence_id for i in sel.items] == ["c1", "c3"]
    assert [e.evidence_id for e in sel.excluded] == ["c2"]
    assert sel.excluded[0].reason is ExclusionReason.DIVERSITY_CAP
    assert sel.items[1].selection_reason is SelectionReason.TOP_RANKED  # same file, second source


def test_selection_reason_marks_spread_vs_top_ranked() -> None:
    candidates = [cand("a1", 1, "aaaa", file="a.py"), cand("a2", 2, "aaaa", file="a.py")]
    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=2)
    assert [i.selection_reason for i in sel.items] == [
        SelectionReason.DIVERSITY_SPREAD,
        SelectionReason.TOP_RANKED,
    ]


def test_deterministic_ordering_regardless_of_input_order() -> None:
    base = [
        cand("e1", 3, "aaaa", file="a.py"),
        cand("e2", 1, "aaaa", file="b.py"),
        cand("e3", 2, "aaaa", file="c.py"),
    ]
    shuffled = [base[2], base[0], base[1]]
    selector = ContextSelector(CharDiv4TokenCounter())
    first = selector.select(base, token_limit=10)
    second = selector.select(shuffled, token_limit=10)
    assert [i.evidence_id for i in first.items] == ["e2", "e3", "e1"]
    assert [i.evidence_id for i in second.items] == ["e2", "e3", "e1"]


def test_exact_counter_default_is_estimated_false() -> None:
    counter = ExactCharCounter()
    sel = ContextSelector(counter).select([cand("e1", 1, "aaa")], token_limit=10)
    assert sel.budget.estimated is False
    assert sel.budget.tokenizer["method"] == "fixed_per_char"
    assert sel.items[0].token_contribution == 3
    heuristic = ContextSelector(CharDiv4TokenCounter()).select(
        [cand("e1", 1, "aaa")], token_limit=10
    )
    assert heuristic.items[0].token_contribution == 1


def test_metadata_is_preserved() -> None:
    candidate = cand(
        "e1",
        1,
        "aaaa",
        file="pkg/mod.py",
        symbol="pkg.mod.fn",
        lines=(3, 5),
        provenance=Provenance.INFERRED,
        source="graph_covered_by",
        revision="b" * 40,
    )
    candidate = candidate.model_copy(
        update={"graph_path": ("seed", "e1"), "expansion_explanation": "COVERED_BY"}
    )
    sel = ContextSelector(CharDiv4TokenCounter()).select([candidate], token_limit=5)
    item = sel.items[0]
    assert item.revision == "b" * 40
    assert item.provenance is Provenance.INFERRED
    assert item.source == "graph_covered_by"
    assert item.file_path == "pkg/mod.py"
    assert item.symbol == "pkg.mod.fn"
    assert item.lines == (3, 5)
    assert item.graph_path == ("seed", "e1")
    assert item.expansion_explanation == "COVERED_BY"


def test_invalid_token_limit_rejected() -> None:
    selector = ContextSelector(CharDiv4TokenCounter())
    with pytest.raises(ValueError):
        selector.select([], token_limit=0)


def test_invalid_caps_rejected() -> None:
    with pytest.raises(ValueError):
        ContextSelector(CharDiv4TokenCounter(), max_items_per_file=0)
    with pytest.raises(ValueError):
        ContextSelector(CharDiv4TokenCounter(), max_items_per_source=0)


def test_selection_model_enforces_budget_bound() -> None:
    budget = ContextBudget(token_limit=1, tokenizer={"name": "x"}, estimated=True)
    with pytest.raises(ValueError):
        ContextSelection(
            items=[],
            excluded=[],
            budget=budget,
            totals=ContextTotals(tokens=2, item_count=0, duplicates=0),
        )


def test_selection_model_enforces_item_count_and_sum() -> None:
    budget = ContextBudget(token_limit=10, tokenizer={"name": "x"}, estimated=True)
    with pytest.raises(ValueError):
        ContextSelection(
            items=[],
            excluded=[],
            budget=budget,
            totals=ContextTotals(tokens=0, item_count=1, duplicates=0),
        )


def test_integration_with_graph_guided_and_graph_paths(mini_repo: Path, mini_repo_url: str) -> None:
    ingested = ingest_repository(mini_repo, mini_repo_url, ingested_at="2026-10-16T00:00:00+00:00")
    corpus = build_function_corpus(mini_repo, ingested.nodes)
    lexical = LexicalBM25Strategy(corpus)
    provider = SnapshotNeighborhoodProvider(ingested.nodes, ingested.edges, direction="out")
    strategy = GraphGuidedStrategy(provider, lexical, seed_count=1)
    query = RetrievalQuery(
        case_id="c",
        text="accumulate values loop total",
        revision=ingested.revision,
        k=5,
        limits=RetrievalLimits(max_items=10, max_hops=1, timeout_ms=5000),
    )
    result = strategy.retrieve(query)

    candidates = []
    for item in result.items:
        path = strategy.explain(item.evidence_id)
        candidates.append(
            ContextCandidate.from_item(
                item,
                content=f"{item.target.file}::{item.target.symbol}",
                graph_path=path.node_ids if path is not None else None,
                expansion_explanation=path.source_label if path is not None else None,
            )
        )

    sel = ContextSelector(CharDiv4TokenCounter()).select(candidates, token_limit=1000)
    assert sel.totals.tokens <= sel.budget.token_limit
    assert all(i.revision == ingested.revision for i in sel.items)
    assert any(i.graph_path is not None for i in sel.items)
    assert sel.totals.item_count == len(sel.items)

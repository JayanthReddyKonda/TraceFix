"""Context manifest tests (A5): invariants, traceability, determinism, handoff."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tracefix.graph.models import Provenance
from tracefix.retrieval.context_selector import (
    CharDiv4TokenCounter,
    ContextBudget,
    ContextCandidate,
    ContextSelection,
    ContextSelector,
    ContextTotals,
    SelectionReason,
)
from tracefix.retrieval.interfaces import (
    EvidenceTarget,
    RankedItem,
    RetrievalResult,
)
from tracefix.retrieval.manifest import (
    Budget,
    ContextManifest,
    EvidenceItem,
    ManifestError,
    Totals,
    build_manifest,
    item_from_selected,
)

REV = "a" * 40


def make_item(
    eid: str,
    rank: int,
    *,
    file: str = "m.py",
    symbol: str | None = None,
    lines: tuple[int, int] | None = None,
    strategy: str = "lexical",
    source: str = "bm25",
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
    """Exact counter double: one token per character (estimated=false)."""

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


def select(candidates: list[ContextCandidate], limit: int, counter: Any = None) -> ContextSelection:
    counter = counter or CharDiv4TokenCounter()
    return ContextSelector(counter).select(candidates, token_limit=limit)


def empty_selection(token_limit: int = 100) -> ContextSelection:
    return ContextSelection(
        items=[],
        totals=ContextTotals(tokens=0, item_count=0, duplicates=0),
        budget=ContextBudget(
            token_limit=token_limit,
            tokenizer=CharDiv4TokenCounter().config(),
            estimated=True,
        ),
        config={},
    )


# --- empty / boundary -------------------------------------------------------


def test_empty_selection_requires_revision() -> None:
    with pytest.raises(ManifestError):
        build_manifest(empty_selection())


def test_empty_selection_with_revision_is_valid() -> None:
    manifest = build_manifest(
        empty_selection(), repo="https://github.com/psf/requests", revision=REV
    )
    assert manifest.items == []
    assert manifest.totals.item_count == 0
    assert manifest.totals.tokens == 0
    assert manifest.revision == REV


def test_full_budget_and_item_count_accounting() -> None:
    cands = [
        ContextCandidate.from_item(make_item(f"e{i}", i + 1), content="x" * (4 * (i + 1)))
        for i in range(3)
    ]
    selection = ContextSelector(CharDiv4TokenCounter()).select(cands, token_limit=24)
    manifest = build_manifest(selection, repo="repo", revision=REV)
    assert manifest.totals.item_count == len(manifest.items)
    assert manifest.totals.tokens == sum(i.token_contribution for i in manifest.items)
    assert manifest.totals.tokens <= manifest.budget.token_limit


# --- exact vs estimated -----------------------------------------------------


def test_tokenizer_exact_label_preserved() -> None:
    cand = ContextCandidate.from_item(make_item("e1", 1), content="abcd")
    selection = ContextSelector(_ExactCounter()).select([cand], token_limit=100)
    manifest = build_manifest(selection, revision=REV)
    assert manifest.budget.estimated is False
    assert manifest.budget.tokenizer["method"] == "fixed_per_char"


def test_tokenizer_estimate_label_preserved() -> None:
    cand = ContextCandidate.from_item(make_item("e1", 1), content="abcd")
    selection = ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)
    manifest = build_manifest(selection, revision=REV)
    assert manifest.budget.estimated is True
    assert manifest.budget.tokenizer["method"] == "char_div_4"


class _ExactCounter:
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


# --- traceability -----------------------------------------------------------


def test_graph_path_and_expansion_preserved_and_explained() -> None:
    cand = ContextCandidate.from_item(
        make_item("e1", 1, strategy="graph_guided", source="graph_callers"),
        content="body",
        graph_path=("n1", "CALLS", "n2"),
        expansion_explanation="reached via caller edge",
        evidence_type="function_body",
    )
    selection = ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)
    manifest = build_manifest(selection, repo="repo", revision=REV)
    assert manifest.items[0].graph_path == ("n1", "CALLS", "n2")
    assert manifest.items[0].expansion_explanation == "reached via caller edge"
    assert manifest.items[0].selection_reason == SelectionReason.DIVERSITY_SPREAD.value
    assert manifest.explain("e1") == ("n1", "CALLS", "n2")
    assert manifest.explain("missing") is None


def test_provenance_and_source_recorded_for_inferred_items() -> None:
    cand = ContextCandidate.from_item(
        make_item("e1", 1, provenance=Provenance.INFERRED),
        content="body",
    )
    selection = ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)
    manifest = build_manifest(selection, revision=REV)
    assert manifest.items[0].provenance == "inferred"
    assert manifest.items[0].source == "bm25"


# --- determinism ------------------------------------------------------------


def test_serialization_is_deterministic() -> None:
    cand = ContextCandidate.from_item(make_item("e1", 1), content="abcd")
    selection = ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)
    manifest = build_manifest(selection, repo="repo", revision=REV)
    first = manifest.to_json()
    second = ContextManifest.model_validate_json(first).to_json()
    assert first == second


def test_roundtrip_preserves_fields() -> None:
    cand = ContextCandidate.from_item(
        make_item("e1", 1, symbol="f", lines=(1, 5)),
        content="abcd",
    )
    selection = ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)
    manifest = build_manifest(selection, repo="repo", revision=REV, case_id="c1")
    restored = ContextManifest.model_validate_json(manifest.to_json())
    assert restored.items[0].symbol == "f"
    assert restored.items[0].lines == (1, 5)
    assert restored.case_id == "c1"


def test_to_json_omits_absent_optional_fields() -> None:
    manifest = build_manifest(empty_selection(), revision=REV)
    payload = manifest.to_json()
    assert "run_id" not in payload
    assert "created_at" not in payload


# --- invariant violations ---------------------------------------------------


def _evidence(eid: str, *, revision: str = REV, **kw: Any) -> EvidenceItem:
    base: dict[str, Any] = dict(
        evidence_id=eid,
        revision=revision,
        file_path="m.py",
        strategy="lexical",
        rank=1,
        score=1.0,
        selection_reason="top_ranked",
        token_contribution=1,
        provenance="observed",
        source="bm25",
    )
    base.update(kw)
    return EvidenceItem(**base)


def _manifest(
    items: list[EvidenceItem], *, tokens: int | None = None, revision: str = REV
) -> ContextManifest:
    return ContextManifest(
        revision=revision,
        budget=Budget(
            token_limit=100,
            tokenizer=CharDiv4TokenCounter().config(),
            estimated=True,
        ),
        items=items,
        totals=Totals(
            tokens=sum(i.token_contribution for i in items) if tokens is None else tokens,
            item_count=len(items),
            duplicates=0,
        ),
    )


def test_duplicate_evidence_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        _manifest([_evidence("e1"), _evidence("e1", rank=2)])


def test_revision_mismatch_rejected() -> None:
    with pytest.raises(ValidationError):
        _manifest([_evidence("e1", revision="b" * 40)])


def test_token_sum_mismatch_rejected() -> None:
    with pytest.raises(ValidationError):
        _manifest([_evidence("e1")], tokens=99)


def test_item_count_mismatch_rejected() -> None:
    manifest = _manifest([_evidence("e1")])
    with pytest.raises(ValidationError):
        ContextManifest(
            revision=manifest.revision,
            budget=manifest.budget,
            items=manifest.items,
            totals=Totals(tokens=1, item_count=5, duplicates=0),
        )


def test_totals_exceeding_budget_rejected() -> None:
    with pytest.raises(ValidationError):
        ContextManifest(
            revision=REV,
            budget=Budget(token_limit=1, tokenizer={}, estimated=True),
            items=[_evidence("e1", token_contribution=5)],
            totals=Totals(tokens=5, item_count=1, duplicates=0),
        )


def test_missing_source_rejected() -> None:
    with pytest.raises(ValidationError):
        _manifest([_evidence("e1", source="")])


def test_missing_provenance_rejected() -> None:
    with pytest.raises(ValidationError):
        _manifest([_evidence("e1", provenance="")])


def test_item_from_selected_maps_fields() -> None:
    cand = ContextCandidate.from_item(make_item("e1", 3, symbol="s", lines=(2, 4)), content="")
    selection = ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)
    mapped = item_from_selected(selection.items[0], repo="repo")
    assert (mapped.evidence_id, mapped.rank, mapped.repo) == ("e1", 3, "repo")
    assert mapped.revision == REV


# --- pipeline handoff -------------------------------------------------------


def test_manifest_from_pipeline_handoff_records_retrieval_config() -> None:
    selection = _selection_with_graph_path()
    retrieval = RetrievalResult(
        items=[make_item("e1", 1)],
        complete=True,
        strategy="fusion",
        config={"strategy": "fusion", "fusion": "rrf", "rrf_k": 60},
        revision=REV,
        elapsed_ms=0.0,
    )
    manifest = build_manifest(selection, retrieval, repo="repo")
    assert manifest.revision == REV
    assert manifest.strategy_config["retrieval"]["fusion"] == "rrf"
    assert "selector" in manifest.strategy_config


def _selection_with_graph_path() -> ContextSelection:
    cand = ContextCandidate.from_item(
        make_item("e1", 1, strategy="graph_guided", source="graph_seed"),
        content="body",
        graph_path=("n1",),
        expansion_explanation="seed",
    )
    return ContextSelector(CharDiv4TokenCounter()).select([cand], token_limit=100)


def test_duplicates_total_is_recorded() -> None:
    selection = ContextSelection(
        items=[],
        totals=ContextTotals(tokens=0, item_count=0, duplicates=2),
        budget=ContextBudget(
            token_limit=100,
            tokenizer=CharDiv4TokenCounter().config(),
            estimated=True,
        ),
        config={},
    )
    manifest = build_manifest(selection, revision=REV)
    assert manifest.totals.duplicates == 2

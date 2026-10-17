"""Dense retrieval adapter tests (A3.4): config boundary, determinism, failures."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from tracefix.retrieval.dense import (
    DenseBackendUnavailableError,
    DenseConfig,
    DenseRetrievalStrategy,
    HashingEmbeddingBackend,
    build_dense_strategy,
)
from tracefix.retrieval.interfaces import PartialReason, RetrievalError
from tracefix.retrieval.lexical import CorpusDocument, make_query

REV = "a" * 40


def doc(eid: str, text: str, *, file: str = "m.py") -> CorpusDocument:
    return CorpusDocument(evidence_id=eid, file=file, symbol=f"m.{eid}", lines=(1, 2), text=text)


class FakeBackend:
    """Deterministic backend returning preset vectors keyed by input text."""

    name = "fake"

    def __init__(
        self,
        dimension: int,
        vectors: dict[str, list[float]],
        *,
        fail_on: str | None = None,
    ) -> None:
        self.dimension = dimension
        self.vectors = vectors
        self.fail_on = fail_on

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if self.fail_on is not None and self.fail_on in texts:
            raise RuntimeError("backend exploded")
        return [self.vectors[text] for text in texts]


def test_disabled_factory_returns_none_and_builds_no_backend() -> None:
    config = DenseConfig(enabled=False)
    assert build_dense_strategy(config, [doc("e1", "alpha")]) is None


def test_enabled_hashing_backend_runs_offline() -> None:
    docs = [doc("e1", "accumulate values"), doc("e2", "unrelated text")]
    strategy = build_dense_strategy(DenseConfig(enabled=True), docs)
    assert isinstance(strategy, DenseRetrievalStrategy)
    result = strategy.retrieve(make_query("accumulate values", revision=REV, k=5))
    assert result.items
    top = result.items[0]
    assert top.evidence_id == "e1"
    assert top.source == "dense" and top.strategy == "dense"
    assert top.source_revision == REV
    assert [i.rank for i in result.items] == list(range(1, len(result.items) + 1))
    assert result.config["backend"] == "hashing"
    assert result.config["estimated"] is True


def test_hashing_backend_is_deterministic() -> None:
    backend = HashingEmbeddingBackend(dimension=32, seed=7)
    first = backend.encode(["alpha beta", "gamma"])
    second = HashingEmbeddingBackend(dimension=32, seed=7).encode(["alpha beta", "gamma"])
    assert first == second
    assert len(first[0]) == 32


def test_empty_corpus_reports_index_incomplete() -> None:
    strategy = build_dense_strategy(DenseConfig(enabled=True), [])
    assert strategy is not None
    result = strategy.retrieve(make_query("anything", revision=REV, k=5))
    assert result.items == []
    assert result.complete is False
    assert result.partial_reason is PartialReason.INDEX_INCOMPLETE


def test_non_matching_query_returns_empty_complete() -> None:
    backend = FakeBackend(2, {"dtext": [1.0, 0.0], "orthogonal-query": [0.0, 1.0]})
    strategy = DenseRetrievalStrategy([doc("e1", "dtext")], backend)
    result = strategy.retrieve(make_query("orthogonal-query", revision=REV, k=5))
    assert result.items == []
    assert result.complete is True


def test_model_backend_without_injection_raises() -> None:
    with pytest.raises(DenseBackendUnavailableError):
        build_dense_strategy(DenseConfig(enabled=True, backend="model", model="some/model"), [])


def test_unknown_backend_raises() -> None:
    with pytest.raises(DenseBackendUnavailableError):
        build_dense_strategy(DenseConfig(enabled=True, backend="nope"), [])


def test_dimension_mismatch_rejected() -> None:
    backend = FakeBackend(2, {"dtext": [1.0, 0.0, 0.0]})
    with pytest.raises(DenseBackendUnavailableError):
        DenseRetrievalStrategy([doc("e1", "dtext")], backend)


def test_backend_embedding_count_mismatch_rejected() -> None:
    class ShortBackend:
        name = "short"
        dimension = 2

        def encode(self, texts: Sequence[str]) -> list[list[float]]:
            return []  # never returns one per text

    with pytest.raises(DenseBackendUnavailableError):
        DenseRetrievalStrategy([doc("e1", "x")], ShortBackend())


def test_query_embedding_failure_raises_retrieval_error() -> None:
    backend = FakeBackend(2, {"dtext": [1.0, 0.0], "q": [1.0, 0.0]}, fail_on="q")
    strategy = DenseRetrievalStrategy([doc("e1", "dtext")], backend)
    with pytest.raises(RetrievalError):
        strategy.retrieve(make_query("q", revision=REV, k=5))


def test_ranking_uses_cosine_and_tie_breaks_by_id() -> None:
    vectors = {
        "q": [1.0, 0.0],
        "t1": [1.0, 0.0],
        "t2": [0.6, 0.8],
        "t3": [1.0, 0.0],
        "t4": [-1.0, 0.0],
    }
    backend = FakeBackend(2, vectors)
    docs = [doc("e1", "t1"), doc("e2", "t2"), doc("e3", "t3"), doc("e4", "t4")]
    result = DenseRetrievalStrategy(docs, backend).retrieve(make_query("q", revision=REV, k=10))
    assert [i.evidence_id for i in result.items] == ["e1", "e3", "e2"]  # e4 (cos<0) dropped
    assert result.items[0].score == pytest.approx(1.0)
    assert result.items[1].score == pytest.approx(1.0)
    assert result.items[2].score == pytest.approx(0.6)


def test_k_limit_reports_limit_reached() -> None:
    vectors = {"q": [1.0, 0.0], "t1": [1.0, 0.0], "t2": [0.6, 0.8]}
    backend = FakeBackend(2, vectors)
    docs = [doc("e1", "t1"), doc("e2", "t2")]
    result = DenseRetrievalStrategy(docs, backend).retrieve(make_query("q", revision=REV, k=1))
    assert len(result.items) == 1
    assert result.partial_reason is PartialReason.LIMIT_REACHED

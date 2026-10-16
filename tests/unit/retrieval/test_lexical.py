"""Lexical BM25 baseline tests (A3.2): determinism, ranking, limits."""

from __future__ import annotations

from pathlib import Path

from tracefix.graph.ingestion import ingest_repository
from tracefix.retrieval.interfaces import PartialReason, RetrievalLimits, RetrievalQuery
from tracefix.retrieval.lexical import LexicalBM25Strategy, build_function_corpus, make_query

REV = "f" * 40


def _strategy(mini_repo: Path, mini_repo_url: str) -> tuple[LexicalBM25Strategy, str]:
    result = ingest_repository(mini_repo, mini_repo_url, ingested_at="2026-10-16T00:00:00+00:00")
    corpus = build_function_corpus(mini_repo, result.nodes)
    return LexicalBM25Strategy(corpus), result.revision


def test_corpus_contains_functions_and_tests(mini_repo: Path, mini_repo_url: str) -> None:
    strategy, _ = _strategy(mini_repo, mini_repo_url)
    symbols = {doc.symbol for doc in strategy.documents}
    assert "calc.core.accumulate" in symbols
    assert "tests.test_core.test_add" in symbols


def test_relevant_function_ranks_first(mini_repo: Path, mini_repo_url: str) -> None:
    strategy, revision = _strategy(mini_repo, mini_repo_url)
    query = make_query("accumulate values loop total", revision=revision, k=3)
    result = strategy.retrieve(query)
    top = result.items[0]
    assert top.target.symbol == "calc.core.accumulate"
    assert top.rank == 1 and top.source == "bm25"
    assert result.complete or result.partial_reason is PartialReason.LIMIT_REACHED


def test_retrieval_is_deterministic(mini_repo: Path, mini_repo_url: str) -> None:
    strategy, revision = _strategy(mini_repo, mini_repo_url)
    query = make_query("sum list items", revision=revision, k=5)
    first = strategy.retrieve(query)
    second = strategy.retrieve(query)
    assert [(i.evidence_id, i.rank, i.score) for i in first.items] == [
        (i.evidence_id, i.rank, i.score) for i in second.items
    ]


def test_k_limits_items(mini_repo: Path, mini_repo_url: str) -> None:
    strategy, revision = _strategy(mini_repo, mini_repo_url)
    result = strategy.retrieve(make_query("test", revision=revision, k=2))
    assert len(result.items) <= 2
    assert result.partial_reason is PartialReason.LIMIT_REACHED


def test_empty_corpus_reports_index_incomplete() -> None:
    strategy = LexicalBM25Strategy([])
    result = strategy.retrieve(make_query("anything", revision=REV, k=5))
    assert result.items == []
    assert result.complete is False
    assert result.partial_reason is PartialReason.INDEX_INCOMPLETE


def test_non_matching_query_returns_empty_complete(mini_repo: Path, mini_repo_url: str) -> None:
    strategy, revision = _strategy(mini_repo, mini_repo_url)
    query = RetrievalQuery(
        case_id="c",
        text="zzzzqqqqxxxx nothing matches this",
        revision=revision,
        k=5,
        limits=RetrievalLimits(max_items=10, max_hops=0, timeout_ms=5000),
    )
    result = strategy.retrieve(query)
    assert result.items == []
    assert result.complete is True


def test_ranks_are_dense_and_ascending(mini_repo: Path, mini_repo_url: str) -> None:
    strategy, revision = _strategy(mini_repo, mini_repo_url)
    result = strategy.retrieve(make_query("calc add multiply", revision=revision, k=10))
    assert [item.rank for item in result.items] == list(range(1, len(result.items) + 1))
    scores = [item.score for item in result.items]
    assert scores == sorted(scores, reverse=True)

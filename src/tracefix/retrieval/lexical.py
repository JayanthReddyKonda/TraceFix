"""Deterministic lexical retrieval baseline (task A3.2).

BM25 (rank_bm25.BM25Okapi) over function-level documents built from an
ingestion snapshot plus the repository checkout. Ranking is deterministic:
equal scores are broken by ascending evidence_id. Tokenization is the
documented scheme `_tokenize`: lowercase, split on non-alphanumerics and
underscores; camelCase is NOT split.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from tracefix.graph.ingestion import module_qualified_name
from tracefix.graph.models import Node, Provenance
from tracefix.retrieval.interfaces import (
    EvidenceTarget,
    PartialReason,
    RankedItem,
    RetrievalLimits,
    RetrievalQuery,
    RetrievalResult,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

SYMBOL_KINDS = ("Function", "Test")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class CorpusDocument:
    evidence_id: str
    file: str
    symbol: str | None
    lines: tuple[int, int] | None
    text: str


def build_function_corpus(repo_root: Path, nodes: dict[str, Node]) -> list[CorpusDocument]:
    """One document per Function/Test node: qualified name + path + source."""
    documents: list[CorpusDocument] = []
    for node in sorted(nodes.values(), key=lambda n: n.entity_id):
        if node.kind not in SYMBOL_KINDS:
            continue
        path = str(node.properties["path"])
        start = int(node.properties["start_line"])
        end = int(node.properties["end_line"])
        full_path = repo_root / path
        try:
            source_lines = full_path.read_text(encoding="utf-8").splitlines()
            segment = "\n".join(source_lines[start - 1 : end])
        except OSError:
            segment = ""
        qn = str(node.properties["qualified_name"])
        text = "\n".join([qn, path, str(node.properties.get("signature", "")), segment])
        documents.append(
            CorpusDocument(
                evidence_id=node.entity_id,
                file=path,
                symbol=qn,
                lines=(start, end),
                text=text,
            )
        )
    return documents


class LexicalBM25Strategy:
    name = "lexical"

    def __init__(self, documents: list[CorpusDocument], k1: float = 1.5, b: float = 0.75) -> None:
        self.documents = documents
        self.k1 = k1
        self.b = b
        self._tokenized = [_tokenize(doc.text) for doc in documents]
        self._bm25: BM25Okapi | None = None
        if documents:
            self._bm25 = BM25Okapi(self._tokenized, k1=k1, b=b)

    @property
    def config(self) -> dict[str, object]:
        return {
            "strategy": self.name,
            "document_count": len(self.documents),
            "k1": self.k1,
            "b": self.b,
            "tokenizer": "lowercase-alnum-underscore (see docs/retrieval/lexical.md)",
        }

    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        started = time.perf_counter()
        limits = query.limits
        take = min(query.k, limits.max_items)
        if self._bm25 is None:
            return RetrievalResult(
                items=[],
                complete=False,
                partial_reason=PartialReason.INDEX_INCOMPLETE,
                strategy=self.name,
                config=self.config,
                revision=query.revision,
                elapsed_ms=_ms(started),
            )
        query_tokens = _tokenize(query.text)
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(
            zip(self.documents, scores, strict=True),
            key=lambda pair: (-float(pair[1]), pair[0].evidence_id),
        )
        items: list[RankedItem] = []
        for doc, score in ranked[:take]:
            if float(score) <= 0.0:
                continue
            items.append(
                RankedItem(
                    evidence_id=doc.evidence_id,
                    strategy=self.name,
                    rank=len(items) + 1,
                    score=float(score),
                    target=EvidenceTarget(
                        file=doc.file,
                        symbol=doc.symbol,
                        lines=doc.lines,
                    ),
                    source_revision=query.revision,
                    provenance=Provenance.OBSERVED,
                    source="bm25",
                )
            )
        elapsed = _ms(started)
        if elapsed > limits.timeout_ms:
            return RetrievalResult(
                items=items,
                complete=False,
                partial_reason=PartialReason.TIMEOUT,
                strategy=self.name,
                config=self.config,
                revision=query.revision,
                elapsed_ms=elapsed,
            )
        matched = sum(1 for _, score in ranked if float(score) > 0.0)
        if matched > len(items):
            return RetrievalResult(
                items=items,
                complete=False,
                partial_reason=PartialReason.LIMIT_REACHED,
                strategy=self.name,
                config=self.config,
                revision=query.revision,
                elapsed_ms=elapsed,
            )
        return RetrievalResult(
            items=items,
            complete=True,
            strategy=self.name,
            config=self.config,
            revision=query.revision,
            elapsed_ms=elapsed,
        )


def make_query(
    text: str,
    revision: str,
    k: int = 10,
    max_items: int = 50,
    case_id: str = "adhoc",
    timeout_ms: int = 5_000,
) -> RetrievalQuery:
    return RetrievalQuery(
        case_id=case_id,
        text=text,
        revision=revision,
        k=k,
        limits=RetrievalLimits(max_items=max_items, max_hops=0, timeout_ms=timeout_ms),
    )


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def corpus_module_qn(path: str) -> str:
    return module_qualified_name(path)

"""Sparse retrieval for Step-1 anchor finding.

We bridge the abstract topic -> concrete email gap with HyDE / Query2Doc style query
expansion (the LLM writes hypothetical emails) and retrieve those against the real
corpus with Okapi BM25. Multiple hypothetical queries are fused with Reciprocal Rank
Fusion (RRF). The deep semantic + binary-state + concealment check is then done by the
LLM fit-judge over the top-k, so BM25 only needs good RECALL into the candidate set.

Dense leg (neural embeddings) is intentionally deferred: no embedder is cached and the
box is offline. `HybridRetriever` keeps a pluggable seam so a dense scorer can be added
later without touching callers.

No third-party deps (no rank_bm25 / faiss / sklearn) — pure stdlib + numpy.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

WORD = re.compile(r"[a-z0-9]{2,}")
STOP = set(
    "a an the of to in for on with by from is are was were be been this that these those "
    "it its as at and or we you they he she his her their our your i not have has had will "
    "would can could should may might must do does did about into over under after before "
    "while which who whom whose what when where why how them then than out up down off no "
    "any all some more most other such only own same but if because so very also just we'll "
    "re fw fwd please thanks thank you let know need want get got would like".split()
)


def tokenize(text: str) -> list[str]:
    return [w for w in WORD.findall((text or "").lower()) if w not in STOP]


class BM25:
    """Okapi BM25 over a fixed document collection."""

    def __init__(self, docs_tokens: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = docs_tokens
        self.N = len(docs_tokens)
        self.doc_len = np.array([len(d) for d in docs_tokens], dtype=float)
        self.avgdl = float(self.doc_len.mean()) if self.N else 0.0
        self.tf = [Counter(d) for d in docs_tokens]
        df = Counter()
        for d in docs_tokens:
            for t in set(d):
                df[t] += 1
        # BM25+ style idf floor keeps very common terms from going negative.
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query_tokens: list[str]) -> np.ndarray:
        s = np.zeros(self.N, dtype=float)
        denom_len = self.k1 * (1 - self.b + self.b * self.doc_len / (self.avgdl or 1.0))
        for t in set(query_tokens):
            idf = self.idf.get(t)
            if idf is None:
                continue
            f = np.array([tf.get(t, 0) for tf in self.tf], dtype=float)
            s += idf * (f * (self.k1 + 1)) / (f + denom_len)
        return s


def rrf_fuse(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion across several ranked id-lists."""
    fused: dict[int, float] = {}
    for ranks in rank_lists:
        for rank, doc_id in enumerate(ranks):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return fused


class HybridRetriever:
    """BM25 retrieval with multi-query RRF fusion. Dense leg is a future seam."""

    def __init__(self, index_texts: list[str]):
        self.docs_tokens = [tokenize(t) for t in index_texts]
        self.bm25 = BM25(self.docs_tokens)

    def retrieve(self, queries: list[str], k: int = 30, per_query: int = 60) -> list[tuple[int, float]]:
        """queries = the HyDE hypothetical-email texts (+ optionally the topic's own
        the binary). Returns [(doc_idx, fused_score)] sorted desc, length<=k."""
        rank_lists: list[list[int]] = []
        for q in queries:
            qt = tokenize(q)
            if not qt:
                continue
            sc = self.bm25.scores(qt)
            top = np.argsort(-sc)[:per_query]
            rank_lists.append([int(i) for i in top if sc[i] > 0])
        if not rank_lists:
            return []
        fused = rrf_fuse(rank_lists)
        ranked = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [(int(i), float(s)) for i, s in ranked]

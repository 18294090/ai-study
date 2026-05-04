from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

from .types import CommunitySummary


class CommunityRetrieveResult(BaseModel):
    community_summaries: List[CommunitySummary]
    query: str


class CommunityRetriever:
    def __init__(self, neo4j_driver, embedder=None, top_k: int = 5):
        self.neo4j_driver = neo4j_driver
        self.embedder = embedder
        self.top_k = top_k

    def retrieve(self, query: str, top_k: int = None) -> CommunityRetrieveResult:
        top_k = top_k or self.top_k

        if self.embedder is None:
            from ...fusion.embedder import Embedder
            self.embedder = Embedder()

        query_embedding = self.embedder.embed([query])[0]

        from ..community_detector import CommunityDetector
        detector = CommunityDetector(self.neo4j_driver, None)

        communities = detector.detect_and_summarize()
        scored = []
        for comm in communities:
            comm_text = comm.summary_text + " " + " ".join(comm.core_concepts)
            comm_embedding = self.embedder.embed([comm_text])[0]
            score = self._cosine_sim(query_embedding, comm_embedding)
            scored.append((score, comm))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_communities = [s[1] for s in scored[:top_k]]

        return CommunityRetrieveResult(
            community_summaries=top_communities,
            query=query,
        )

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
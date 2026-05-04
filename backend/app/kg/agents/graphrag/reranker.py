from __future__ import annotations
from typing import List, Union, Dict, Any, Optional
from pydantic import BaseModel
import os


class RerankResult(BaseModel):
    index: int
    document: Union[str, Dict[str, Any]]
    relevance_score: float


class Reranker:
    def __init__(
        self,
        api_key: str = None,
        model: str = "rerank-v3",
    ):
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            import cohere
            self._client = cohere.Client(self.api_key)
        return self._client

    def rerank(
        self,
        query: str,
        documents: List[Union[str, Dict[str, Any]]],
        top_n: int = 10,
    ) -> List[RerankResult]:
        if not documents:
            return []

        client = self._get_client()
        doc_texts = [d if isinstance(d, str) else d.get("text", str(d)) for d in documents]

        response = client.rerank(
            query=query,
            documents=doc_texts,
            top_n=top_n,
            model=self.model,
            return_documents=False,
        )

        results = []
        for r in response.results:
            results.append(RerankResult(
                index=r.index,
                document=documents[r.index],
                relevance_score=r.relevance_score,
            ))
        return results

    def rerank_hybrid(
        self,
        query: str,
        vector_results: List[Any],
        kg_entities: List[Any],
        top_n: int = 10,
    ) -> List[Any]:
        all_docs = []
        doc_sources = []

        for v in vector_results:
            all_docs.append({"text": v.text, "id": v.chunk_id, "type": "vector"})
            doc_sources.append(("vector", v))

        for e in kg_entities:
            neighbors_text = " ".join([n.target_name for n in e.neighbors])
            all_docs.append({"text": f"{e.name}: {e.description or ''} {neighbors_text}", "id": e.entity_id, "type": "kg"})
            doc_sources.append(("kg", e))

        reranked = self.rerank(query, all_docs, top_n=top_n)

        results = []
        for r in reranked:
            source_type, source_obj = doc_sources[r.index]
            results.append((source_type, source_obj, r.relevance_score))
        return results
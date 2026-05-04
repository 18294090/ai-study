from __future__ import annotations
from typing import List, Union, Dict, Any, Optional
from pydantic import BaseModel
import os


class RerankResult(BaseModel):
    index: int
    document: Union[str, Dict[str, Any]]
    relevance_score: float


SIGNAL_WEIGHTS = {
    "direct_link": 3.0,
    "source_overlap": 4.0,
    "adamic_adar": 1.5,
    "type_affinity": 1.0,
}

RERANK_BLEND = 0.4
GRAPH_BLEND = 0.6


class Reranker:
    def __init__(
        self,
        api_key: str = None,
        model: str = "rerank-v3",
        neo4j_driver=None,
    ):
        self.api_key = api_key or os.environ.get("COHERE_API_KEY", "")
        self.model = model
        self.neo4j_driver = neo4j_driver
        self._client = None

    def _get_cohere_client(self):
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

        client = self._get_cohere_client()
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
        seed_node_ids: List[str] = None,
        top_n: int = 10,
    ) -> List[Any]:
        all_docs = []
        doc_sources = []

        for v in vector_results:
            all_docs.append({"text": v.text, "id": v.chunk_id, "type": "vector"})
            doc_sources.append(("vector", v))

        for e in kg_entities:
            neighbors_text = " ". join([n.target_name for n in e.neighbors])
            all_docs.append({"text": f"{e.name}: {e.description or ''} {neighbors_text}", "id": e.entity_id, "type": "kg"})
            doc_sources.append(("kg", e))

        if not all_docs:
            return []

        reranked = self.rerank(query, all_docs, top_n=len(all_docs))

        rerank_scores = {r.index: r.relevance_score for r in reranked}

        graph_scores = self._compute_graph_signals(
            doc_sources,
            seed_node_ids or [],
        )

        final_scores = []
        for i, (source_type, source_obj) in enumerate(doc_sources):
            rerank_s = rerank_scores.get(i, 0.0)
            graph_s = graph_scores.get(i, 0.0)
            combined = RERANK_BLEND * rerank_s + GRAPH_BLEND * graph_s
            final_scores.append((combined, source_type, source_obj, rerank_s, graph_s))

        final_scores.sort(key=lambda x: x[0], reverse=True)
        return [(source_type, source_obj, final_score, rerank_s, graph_s)
                for final_score, source_type, source_obj, rerank_s, graph_s in final_scores[:top_n]]

    def _compute_graph_signals(
        self,
        doc_sources: List[tuple],
        seed_node_ids: List[str],
    ) -> Dict[int, float]:
        if self.neo4j_driver is None:
            return {i: 0.0 for i in range(len(doc_sources))}

        doc_ids = [src[1].entity_id if src[0] == "kg" else src[1].chunk_id for src in doc_sources]
        doc_types = [src[1].entity_type if src[0] == "kg" else "chunk" for src in doc_sources]
        doc_source_files = [getattr(src[1], "source_file", None) for src in doc_sources]

        scores = {}
        for i in range(len(doc_sources)):
            s = SIGNAL_WEIGHTS["type_affinity"]
            if doc_types[i] in ("concept", "entity") and seed_node_ids:
                for sid in seed_node_ids:
                    s += SIGNAL_WEIGHTS["direct_link"] * self._get_link_strength(doc_ids[i], sid, doc_types[i])
            for j in range(len(doc_sources)):
                if i != j and doc_source_files[i] and doc_source_files[i] == doc_source_files[j]:
                    s += SIGNAL_WEIGHTS["source_overlap"]
            if seed_node_ids:
                s += SIGNAL_WEIGHTS["adamic_adar"] * self._get_adamic_adar(doc_ids[i], seed_node_ids)
            scores[i] = s

        max_s = max(scores.values()) if scores else 1.0
        return {k: v / max_s for k, v in scores.items()}

    def _get_link_strength(self, node_a: str, node_b: str, node_type: str) -> float:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (a)-[r]->(b) WHERE a.id = $a AND b.id = $b RETURN count(r) as c",
                    a=node_a, b=node_b
                )
                data = result.data()
                return float(data[0]["c"]) if data else 0.0
        except Exception:
            return 0.0

    def _get_adamic_adar(self, node: str, seed_nodes: List[str]) -> float:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n)-[r1]-(mid)-[r2]-(seed) "
                    "WHERE n.id = $node AND seed.id IN $seeds AND mid <> n AND mid <> seed "
                    "RETURN count(DISTINCT mid) as common_neighbors",
                    node=node, seeds=seed_nodes
                )
                data = result.data()
                common = float(data[0]["common_neighbors"]) if data else 0.0
                return 1.0 / (common + 1.0)
        except Exception:
            return 0.0
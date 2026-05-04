from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

from .types import RetrievedChunk, RetrievedEntity, EntityEdge


class HybridRetrieveResult(BaseModel):
    vector_results: List[RetrievedChunk]
    kg_entities: List[RetrievedEntity]
    query: str


class HybridRetriever:
    def __init__(
        self,
        qdrant_client,
        neo4j_driver,
        embedder=None,
        vector_top_k: int = 30,
    ):
        self.qdrant_client = qdrant_client
        self.neo4j_driver = neo4j_driver
        self.embedder = embedder
        self.vector_top_k = vector_top_k

    def retrieve(self, query: str, top_k: int = None) -> HybridRetrieveResult:
        if self.embedder is None:
            from ...fusion.embedder import Embedder
            self.embedder = Embedder()

        query_embedding = self.embedder.embed([query])[0]

        vector_results = self._vector_search(query_embedding, top_k or self.vector_top_k)
        kg_entities = self._kg_expand(query, top_k or self.vector_top_k)

        return HybridRetrieveResult(
            vector_results=vector_results,
            kg_entities=kg_entities,
            query=query,
        )

    def _vector_search(self, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]:
        try:
            results = self.qdrant_client.search(
                collection_name="kg_nodes",
                query_vector=query_embedding,
                limit=top_k,
            )
            chunks = []
            for r in results:
                chunks.append(RetrievedChunk(
                    chunk_id=r.id,
                    text=r.payload.get("text", ""),
                    score=r.score,
                    community_id=r.payload.get("community_id"),
                ))
            return chunks
        except Exception:
            return []

    def _kg_expand(self, query: str, top_k: int) -> List[RetrievedEntity]:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n) WHERE n.name CONTAINS $query "
                    "RETURN n.id AS id, n.name AS name, labels(n)[0] AS type "
                    "LIMIT $top_k",
                    query=query, top_k=top_k
                )
                entities = []
                for record in result:
                    neighbors = self._get_neighbors(record["id"])
                    entities.append(RetrievedEntity(
                        entity_id=record["id"],
                        name=record["name"],
                        entity_type=record["type"],
                        neighbors=neighbors,
                        score=1.0,
                    ))
                return entities
        except Exception:
            return []

    def _get_neighbors(self, node_id: str) -> List[EntityEdge]:
        try:
            with self.neo4j_driver.session(database="neo4j") as session:
                result = session.run(
                    "MATCH (n)-[r]->(m) WHERE n.id = $id "
                    "RETURN m.id AS target_id, m.name AS target_name, type(r) AS rel_type "
                    "LIMIT 5",
                    id=node_id
                )
                return [
                    EntityEdge(
                        target_id=r["target_id"],
                        target_name=r["target_name"],
                        relation_type=r["rel_type"],
                    )
                    for r in result
                ]
        except Exception:
            return []

from __future__ import annotations

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
import logging
import numpy as np

try:
    from qdrant_client import QdrantClient as _QdrantClient
    from qdrant_client.http import models as _models
    QDRANT_AVAILABLE = True
    QdrantClient = _QdrantClient
    models = _models
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None

from ..fusion.embedder import Embedder
from ..models import Entity, TextbookAnchor

logger = logging.getLogger(__name__)

KG_NODES_COLLECTION = "kg_nodes"
KG_COMMUNITIES_COLLECTION = "kg_communities"


@dataclass
class QdrantWriter:
    host: str = "localhost"
    port: int = 6333
    embedder: Optional[Embedder] = None
    _client: Optional[QdrantClient] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        if not QDRANT_AVAILABLE:
            raise RuntimeError("qdrant_client not installed. Install with: pip install qdrant-client")
        self._client = QdrantClient(host=self.host, port=self.port)
        if self.embedder is None:
            self.embedder = Embedder()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_collections(self):
        existing = {c.name for c in self._client.get_collections().collections}
        if KG_NODES_COLLECTION not in existing:
            self._client.create_collection(
                collection_name=KG_NODES_COLLECTION,
                vectors_config={
                    "dense": models.VectorParams(
                        size=1024,
                        distance=models.Distance.COSINE,
                    )
                },
            )
            logger.info(f"Created collection: {KG_NODES_COLLECTION}")
        if KG_COMMUNITIES_COLLECTION not in existing:
            self._client.create_collection(
                collection_name=KG_COMMUNITIES_COLLECTION,
                vectors_config={
                    "dense": models.VectorParams(
                        size=1024,
                        distance=models.Distance.COSINE,
                    )
                },
            )
            logger.info(f"Created collection: {KG_COMMUNITIES_COLLECTION}")

    def init_schema(self):
        self._ensure_collections()

    def _anchor_payload(self, anchor: Optional[TextbookAnchor]) -> Dict[str, Any]:
        if not anchor:
            return {}
        return {
            "textbook_id": anchor.textbook_id,
            "chapter_id": anchor.chapter_id,
            "paragraph_offset": anchor.paragraph_offset,
            "page": anchor.page,
        }

    def _entity_payload(self, entity: Entity) -> Dict[str, Any]:
        return {
            "name": entity.name,
            "type": entity.type.value,
            "layer": entity.layer,
            "description": entity.description,
            "latex": entity.latex,
            "community_id": entity.community_id,
            "anchor": self._anchor_payload(entity.anchor),
        }

    def write_node(self, entity: Entity) -> bool:
        texts = [entity.name]
        if entity.description:
            texts.append(entity.description)
        vectors = self.embedder.encode(texts)
        dense_vec = vectors[0].tolist() if len(vectors) > 0 else np.zeros(1024).tolist()

        payload = self._entity_payload(entity)
        self._client.upsert(
            collection_name=KG_NODES_COLLECTION,
            points=[
                models.PointStruct(
                    id=entity.id,
                    vector={"dense": dense_vec},
                    payload=payload,
                )
            ],
        )
        return True

    def write_nodes_batch(self, entities: List[Entity]) -> int:
        if not entities:
            return 0
        texts = [e.name for e in entities]
        descs = [e.description or "" for e in entities]
        all_texts = [t + " " + d for t, d in zip(texts, descs)]
        vectors = self.embedder.encode(all_texts)

        points = []
        for i, entity in enumerate(entities):
            payload = self._entity_payload(entity)
            dense_vec = vectors[i].tolist() if i < len(vectors) else np.zeros(1024).tolist()
            points.append(
                models.PointStruct(
                    id=entity.id,
                    vector={"dense": dense_vec},
                    payload=payload,
                )
            )
        self._client.upsert(
            collection_name=KG_NODES_COLLECTION,
            points=points,
        )
        return len(points)

    def write_community_summary(
        self,
        community_id: str,
        level: int,
        summary: str,
    ) -> bool:
        texts = [summary]
        vectors = self.embedder.encode(texts)
        dense_vec = vectors[0].tolist() if len(vectors) > 0 else np.zeros(1024).tolist()

        payload = {
            "community_id": community_id,
            "level": level,
            "summary": summary,
        }
        self._client.upsert(
            collection_name=KG_COMMUNITIES_COLLECTION,
            points=[
                models.PointStruct(
                    id=community_id,
                    vector={"dense": dense_vec},
                    payload=payload,
                )
            ],
        )
        return True

    def write_communities_batch(
        self,
        communities: List[Dict[str, Any]],
    ) -> int:
        if not communities:
            return 0
        summaries = [c["summary"] for c in communities]
        vectors = self.embedder.encode(summaries)

        points = []
        for i, comm in enumerate(communities):
            dense_vec = vectors[i].tolist() if i < len(vectors) else np.zeros(1024).tolist()
            points.append(
                models.PointStruct(
                    id=comm["community_id"],
                    vector={"dense": dense_vec},
                    payload={
                        "community_id": comm["community_id"],
                        "level": comm["level"],
                        "summary": comm["summary"],
                    },
                )
            )
        self._client.upsert(
            collection_name=KG_COMMUNITIES_COLLECTION,
            points=points,
        )
        return len(points)

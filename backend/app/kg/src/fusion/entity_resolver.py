from typing import List, Dict, Callable, Optional
import numpy as np

from src.models.entities import Entity
from src.fusion.embedder import Embedder


class EntityResolver:
    def __init__(
        self,
        embedder: Embedder,
        verifier_fn: Callable[[Entity, Entity], bool],
        sim_threshold: float = 0.85,
        ambiguous_band: tuple = (0.75, 0.85),
    ):
        self.embedder = embedder
        self.verifier_fn = verifier_fn
        self.sim_threshold = sim_threshold
        self.ambiguous_band = ambiguous_band

    def cluster(self, entities: List[Entity]) -> List[List[Entity]]:
        if not entities:
            return []

        type_buckets = self._bucket_by_type(entities)

        clusters: List[List[Entity]] = []
        for bucket_entities in type_buckets.values():
            clusters.extend(self._cluster_bucket(bucket_entities))

        return clusters

    def _bucket_by_type(self, entities: List[Entity]) -> Dict[str, List[Entity]]:
        buckets: Dict[str, List[Entity]] = {}
        for entity in entities:
            entity_type = getattr(entity, 'type', 'unknown')
            if entity_type not in buckets:
                buckets[entity_type] = []
            buckets[entity_type].append(entity)
        return buckets

    def _cluster_bucket(self, entities: List[Entity]) -> List[List[Entity]]:
        if len(entities) <= 1:
            return [entities] if entities else []

        texts = [e.name for e in entities]
        embeddings = self.embedder.encode(texts)

        n = len(entities)
        similarity_matrix = np.dot(embeddings, embeddings.T)

        visited = [False] * n
        clusters: List[List[Entity]] = []

        for i in range(n):
            if visited[i]:
                continue

            cluster = [entities[i]]
            visited[i] = True

            for j in range(i + 1, n):
                if visited[j]:
                    continue

                sim = similarity_matrix[i][j]
                if sim >= self.sim_threshold:
                    cluster.append(entities[j])
                    visited[j] = True
                elif self.ambiguous_band[0] <= sim < self.ambiguous_band[1]:
                    if self.verifier_fn(entities[i], entities[j]):
                        cluster.append(entities[j])
                        visited[j] = True

            clusters.append(cluster)

        return clusters
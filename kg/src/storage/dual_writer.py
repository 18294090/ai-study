from __future__ import annotations

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from .neo4j_writer import Neo4jWriter
from .qdrant_writer import QdrantWriter

logger = logging.getLogger(__name__)


class WriteOp(str, Enum):
    ENTITY = "entity"
    TRIPLE = "triple"
    COMMUNITY = "community"


@dataclass
class DeadLetterEntry:
    operation: WriteOp
    payload: Dict[str, Any]
    error: str
    timestamp: str


@dataclass
class DualWriter:
    neo4j: Neo4jWriter
    qdrant: QdrantWriter
    _dead_letter_queue: List[DeadLetterEntry] = field(default_factory=list, init=False)

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def write_entity(self, entity) -> bool:
        try:
            self.neo4j.write_entity(entity)
        except Exception as e:
            logger.error(f"Neo4j entity write failed for {entity.id}: {e}")
            self._dead_letter_queue.append(
                DeadLetterEntry(
                    operation=WriteOp.ENTITY,
                    payload={"entity_id": entity.id, "entity": entity.model_dump()},
                    error=str(e),
                    timestamp=self._now_iso(),
                )
            )
            raise

        try:
            self.qdrant.write_node(entity)
        except Exception as e:
            logger.error(f"Qdrant node write failed for {entity.id}, rolling back Neo4j: {e}")
            self._rollback_entity(entity)
            self._dead_letter_queue.append(
                DeadLetterEntry(
                    operation=WriteOp.ENTITY,
                    payload={"entity_id": entity.id, "entity": entity.model_dump()},
                    error=f"Qdrant failed after Neo4j success: {e}",
                    timestamp=self._now_iso(),
                )
            )
            raise

        return True

    def write_entities_batch(self, entities) -> int:
        written = 0
        try:
            written = self.neo4j.write_entities_batch(entities)
        except Exception as e:
            logger.error(f"Neo4j batch entity write failed: {e}")
            for entity in entities:
                try:
                    self.write_entity(entity)
                    written += 1
                except Exception:
                    pass
            return written

        try:
            self.qdrant.write_nodes_batch(entities)
        except Exception as e:
            logger.error(f"Qdrant batch node write failed, rolling back: {e}")
            for entity in entities:
                self._rollback_entity(entity)
            raise

        return written

    def write_triple(self, triple) -> bool:
        try:
            self.neo4j.write_triple(triple)
        except Exception as e:
            logger.error(f"Neo4j triple write failed: {e}")
            self._dead_letter_queue.append(
                DeadLetterEntry(
                    operation=WriteOp.TRIPLE,
                    payload={"triple": triple.model_dump()},
                    error=str(e),
                    timestamp=self._now_iso(),
                )
            )
            raise

        try:
            self.qdrant.write_node(triple.subject)
            self.qdrant.write_node(triple.object)
        except Exception as e:
            logger.warning(f"Qdrant node write for triple failed (non-critical): {e}")

        return True

    def write_triples_batch(self, triples) -> int:
        written = 0
        try:
            written = self.neo4j.write_triples_batch(triples)
        except Exception as e:
            logger.error(f"Neo4j batch triple write failed: {e}")
            for triple in triples:
                try:
                    self.write_triple(triple)
                    written += 1
                except Exception:
                    pass
            return written

        try:
            all_entities = []
            for t in triples:
                all_entities.append(t.subject)
                all_entities.append(t.object)
            self.qdrant.write_nodes_batch(all_entities)
        except Exception as e:
            logger.warning(f"Qdrant batch node write for triples failed (non-critical): {e}")

        return written

    def write_community_summary(self, community_id: str, level: int, summary: str) -> bool:
        try:
            self.neo4j.write_community(community_id, level, summary)
        except Exception as e:
            logger.error(f"Neo4j community write failed for {community_id}: {e}")
            self._dead_letter_queue.append(
                DeadLetterEntry(
                    operation=WriteOp.COMMUNITY,
                    payload={"community_id": community_id, "level": level, "summary": summary},
                    error=str(e),
                    timestamp=self._now_iso(),
                )
            )
            raise

        try:
            self.qdrant.write_community_summary(community_id, level, summary)
        except Exception as e:
            logger.error(f"Qdrant community write failed for {community_id}, rolling back: {e}")
            self._rollback_community(community_id)
            self._dead_letter_queue.append(
                DeadLetterEntry(
                    operation=WriteOp.COMMUNITY,
                    payload={"community_id": community_id, "level": level, "summary": summary},
                    error=f"Qdrant failed after Neo4j success: {e}",
                    timestamp=self._now_iso(),
                )
            )
            raise

        return True

    def _rollback_entity(self, entity):
        with self.neo4j._driver.session(database=self.neo4j.database) as session:
            labels = self.neo4j._entity_labels(entity)
            session.run(f"MATCH (n{labels} {entity.id}) DELETE n")

    def _rollback_community(self, community_id: str):
        with self.neo4j._driver.session(database=self.neo4j.database) as session:
            session.run("MATCH (c:community {id: $id}) DELETE c", id=community_id)

    def get_dead_letters(self) -> List[Dict[str, Any]]:
        return [
            {
                "operation": dl.operation.value,
                "payload": dl.payload,
                "error": dl.error,
                "timestamp": dl.timestamp,
            }
            for dl in self._dead_letter_queue
        ]

    def clear_dead_letters(self):
        self._dead_letter_queue.clear()

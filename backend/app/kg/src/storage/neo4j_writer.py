from __future__ import annotations

from typing import List, Optional
from dataclasses import dataclass, field
import logging

from neo4j import GraphDatabase

from ..models import Entity, KnowledgeTriple, TextbookAnchor

logger = logging.getLogger(__name__)


@dataclass
class Neo4jWriter:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    _driver: Optional[object] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self._driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )

    def close(self):
        if self._driver:
            self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _ensure_constraints(self, session):
        session.run(
            "CREATE CONSTRAINT FOR (n:concept) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:formula) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:theorem) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:person) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:event) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:location) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:work) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:time) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        session.run(
            "CREATE CONSTRAINT FOR (n:dataset) REQUIRE n.id IS UNIQUE IF NOT EXISTS"
        )
        logger.info("Neo4j constraints ensured")

    def init_schema(self):
        with self._driver.session(database=self.database) as session:
            self._ensure_constraints(session)
            self.init_oplog_schema()

    def init_oplog_schema(self):
        with self._driver.session(database=self.database) as session:
            session.run("CREATE INDEX FOR (l:OperationLog) ON (l.timestamp) IF NOT EXISTS")
            session.run("CREATE INDEX FOR (l:OperationLog) ON (l.target_id) IF NOT EXISTS")
            session.run("CREATE INDEX FOR (l:OperationLog) ON (l.operation) IF NOT EXISTS")
        logger.info("OperationLog schema ensured")

    def log_operation(
        self,
        operation: str,
        target_id: str,
        target_type: str,
        user_id: str = "system",
        details: str = "{}",
        textbook_id: str = None,
        reasoning: str = "",
    ) -> bool:
        with self._driver.session(database=self.database) as session:
            cypher = """
            CREATE (l:OperationLog {
                timestamp: datetime(),
                operation: $operation,
                target_id: $target_id,
                target_type: $target_type,
                user_id: $user_id,
                details: $details,
                textbook_id: $textbook_id,
                reasoning: $reasoning
            })
            RETURN l
            """
            session.run(
                cypher,
                operation=operation,
                target_id=target_id,
                target_type=target_type,
                user_id=user_id,
                details=details,
                textbook_id=textbook_id,
                reasoning=reasoning,
            )
        return True

    def _entity_labels(self, entity) -> str:
        type_label = entity.type.value
        layer_label = getattr(entity, "layer", "domain")
        return f":{type_label}:{layer_label}"

    def _anchor_props(self, anchor: Optional[TextbookAnchor]) -> dict:
        if not anchor:
            return {}
        return {
            "textbook_id": anchor.textbook_id,
            "chapter_id": anchor.chapter_id,
            "paragraph_offset": anchor.paragraph_offset,
            "page": anchor.page,
        }

    def write_entity(self, entity: Entity) -> bool:
        with self._driver.session(database=self.database) as session:
            labels = self._entity_labels(entity)
            props = {
                "id": entity.id,
                "name": entity.name,
                "confidence": entity.confidence,
                "description": entity.description,
                "latex": entity.latex,
                "community_id": entity.community_id,
                **self._anchor_props(entity.anchor),
            }
            props = {k: v for k, v in props.items() if v is not None}
            cypher = f"CREATE (n{labels} $props) RETURN n"
            session.run(cypher, props=props)
        self.log_operation(
            operation="create_entity",
            target_id=entity.id,
            target_type="entity",
            user_id=getattr(entity, "created_by", "system"),
            details=entity.model_dump_json(),
            textbook_id=getattr(entity.anchor, "textbook_id", None) if entity.anchor else None,
        )
        return True

    def write_entities_batch(self, entities: List[Entity]) -> int:
        if not entities:
            return 0
        with self._driver.session(database=self.database) as session:
            data = []
            for e in entities:
                labels = self._entity_labels(e)
                props = {
                    "id": e.id,
                    "name": e.name,
                    "confidence": e.confidence,
                    "description": e.description,
                    "latex": e.latex,
                    "community_id": e.community_id,
                    **self._anchor_props(e.anchor),
                }
                props = {k: v for k, v in props.items() if v is not None}
                data.append({"labels": labels, "props": props})
            cypher = """
            UNWIND $data AS row
            CREATE (n=row.labels, p=row.props)
            RETURN count(n) AS written
            """
            result = session.run(cypher, data=data)
            return result.single()["written"]

    def write_triple(self, triple: KnowledgeTriple) -> bool:
        with self._driver.session(database=self.database) as session:
            s_labels = self._entity_labels(triple.subject)
            o_labels = self._entity_labels(triple.object)
            s_props = {
                "id": triple.subject.id,
                "name": triple.subject.name,
                "type": triple.subject.type.value,
            }
            o_props = {
                "id": triple.object.id,
                "name": triple.object.name,
                "type": triple.object.type.value,
            }
            rel_props = {
                "predicate": triple.predicate.value,
                "confidence": triple.confidence,
                "extracted_by": triple.extracted_by,
                "verified_by": triple.verified_by,
                **self._anchor_props(triple.anchor),
            }
            rel_props = {k: v for k, v in rel_props.items() if v is not None}
            cypher = """
            MERGE (s%s {id: $s_id})
            ON CREATE SET s.name = $s_name, s.type = $s_type
            MERGE (o%s {id: $o_id})
            ON CREATE SET o.name = $o_name, o.type = $o_type
            CREATE (s)-[r:`%s` %s]->(o)
            RETURN r
            """ % (
                s_labels, o_labels, triple.predicate.value,
                "{" + ", ".join(f"{k}: ${k}" for k in rel_props) + "}" if rel_props else ""
            )
            params = {
                "s_id": triple.subject.id,
                "s_name": triple.subject.name,
                "s_type": triple.subject.type.value,
                "o_id": triple.object.id,
                "o_name": triple.object.name,
                "o_type": triple.object.type.value,
                **rel_props,
            }
            session.run(cypher, **params)
        self.log_operation(
            operation="create_triple",
            target_id=f"{triple.subject.id}-{triple.predicate.value}-{triple.object.id}",
            target_type="triple",
            user_id=triple.extracted_by or "system",
            details=triple.model_dump_json(),
            textbook_id=getattr(triple.anchor, "textbook_id", None) if triple.anchor else None,
        )
        return True

    def write_triples_batch(self, triples: List[KnowledgeTriple]) -> int:
        if not triples:
            return 0
        with self._driver.session(database=self.database) as session:
            data = []
            for t in triples:
                s_labels = self._entity_labels(t.subject)
                o_labels = self._entity_labels(t.object)
                rel_props = {
                    "predicate": t.predicate.value,
                    "confidence": t.confidence,
                    "extracted_by": t.extracted_by,
                    "verified_by": t.verified_by,
                    **self._anchor_props(t.anchor),
                }
                rel_props = {k: v for k, v in rel_props.items() if v is not None}
                data.append({
                    "s_labels": s_labels,
                    "o_labels": o_labels,
                    "s_id": t.subject.id,
                    "s_name": t.subject.name,
                    "s_type": t.subject.type.value,
                    "o_id": t.object.id,
                    "o_name": t.object.name,
                    "o_type": t.object.type.value,
                    "rel_props": rel_props,
                })
            cypher = """
            UNWIND $data AS row
            MERGE (s:row.s_labels {id: row.s_id})
            ON CREATE SET s.name = row.s_name, s.type = row.s_type
            MERGE (o:row.o_labels {id: row.o_id})
            ON CREATE SET o.name = row.o_name, o.type = row.o_type
            CREATE (s)-[r:`row.rel_props.predicate`]->(o)
            WITH row, r
            UNWIND keys(row.rel_props) AS key
            WHERE key <> 'predicate'
            SET r[key] = row.rel_props[key]
            RETURN count(r) AS written
            """
            result = session.run(cypher, data=data)
            return result.single()["written"]

    def write_community(self, community_id: str, level: int, summary: str) -> bool:
        with self._driver.session(database=self.database) as session:
            cypher = """
            MERGE (c:community {id: $community_id})
            SET c.level = $level, c.summary = $summary
            RETURN c
            """
            session.run(cypher, community_id=community_id, level=level, summary=summary)
        return True

from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class ToolResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    operation_id: Optional[str] = None
    timestamp: datetime


class KGQueryRequest(BaseModel):
    question: str
    agent_id: str
    session_id: str


class KGCreateEntityRequest(BaseModel):
    name: str
    entity_type: str
    properties: dict
    agent_id: str
    session_id: str


class KGUpdateEntityRequest(BaseModel):
    entity_id: str
    properties: dict
    agent_id: str
    session_id: str


class KGDeleteEntityRequest(BaseModel):
    entity_id: str
    agent_id: str
    session_id: str


class KGCreateRelationRequest(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    properties: dict
    agent_id: str
    session_id: str


class KGDeleteRelationRequest(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    agent_id: str
    session_id: str


async def kg_query(question: str, agent_id: str, session_id: str) -> ToolResponse:
    """Query knowledge graph for answers"""
    operation_id = str(uuid.uuid4())
    try:
        from app.kg.agents.graphrag_service import GraphRAGService

        service = GraphRAGService(
            neo4j_driver=None,
            qdrant_client=None,
        )
        result = await service.query(question)

        return ToolResponse(
            success=True,
            data={
                "answer": result.answer,
                "citations": [c.model_dump() for c in result.citations] if result.citations else [],
                "kg_paths": result.kg_paths,
                "intent": result.intent.value if hasattr(result.intent, 'value') else str(result.intent),
                "retrieval_type": result.retrieval_type,
            },
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"kg_query failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def kg_create_entity(
    name: str,
    entity_type: str,
    properties: dict,
    agent_id: str,
    session_id: str,
) -> ToolResponse:
    """Create entity in knowledge graph"""
    operation_id = str(uuid.uuid4())
    try:
        from app.kg.src.storage.neo4j_writer import Neo4jWriter
        from app.kg.src.models.entities import Entity

        entity_id = str(uuid.uuid4())
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            properties=properties,
        )

        writer = Neo4jWriter()
        writer.init_schema()

        with writer._driver.session(database=writer.database) as session:
            cypher = """
            MATCH (existing {name: $name, entity_type: $entity_type})
            WHERE existing.id IS NOT NULL
            RETURN existing LIMIT 1
            """
            existing = session.run(cypher, name=name, entity_type=entity_type).single()
            if existing:
                return ToolResponse(
                    success=False,
                    error=f"Entity with name '{name}' and type '{entity_type}' already exists",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

        writer.write_entity(entity)

        writer.log_operation(
            operation="CREATE_ENTITY",
            target_id=entity_id,
            target_type="Entity",
            user_id=agent_id,
            details=entity.model_dump_json(),
        )

        return ToolResponse(
            success=True,
            data={
                "entity_id": entity_id,
                "name": name,
                "entity_type": entity_type,
                "properties": properties,
            },
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"kg_create_entity failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def kg_update_entity(
    entity_id: str,
    properties: dict,
    agent_id: str,
    session_id: str,
) -> ToolResponse:
    """Update entity in knowledge graph"""
    operation_id = str(uuid.uuid4())
    try:
        from app.kg.src.storage.neo4j_writer import Neo4jWriter

        writer = Neo4jWriter()

        with writer._driver.session(database=writer.database) as session:
            check_cypher = "MATCH (e) WHERE e.id = $entity_id RETURN e LIMIT 1"
            existing = session.run(check_cypher, entity_id=entity_id).single()
            if not existing:
                return ToolResponse(
                    success=False,
                    error=f"Entity with id '{entity_id}' not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

        set_clause = ", ".join([f"e.{k} = ${k}" for k in properties.keys()])
        params = {"entity_id": entity_id, **properties}
        update_cypher = f"MATCH (e) WHERE e.id = $entity_id SET {set_clause}"

        with writer._driver.session(database=writer.database) as session:
            session.run(update_cypher, **params)

        writer.log_operation(
            operation="UPDATE_ENTITY",
            target_id=entity_id,
            target_type="Entity",
            user_id=agent_id,
            details=str(properties),
        )

        return ToolResponse(
            success=True,
            data={
                "entity_id": entity_id,
                "updated_properties": properties,
            },
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"kg_update_entity failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def kg_delete_entity(
    entity_id: str,
    agent_id: str,
    session_id: str,
) -> ToolResponse:
    """Delete entity from knowledge graph"""
    operation_id = str(uuid.uuid4())
    try:
        from app.kg.src.storage.neo4j_writer import Neo4jWriter

        writer = Neo4jWriter()

        with writer._driver.session(database=writer.database) as session:
            check_cypher = "MATCH (e) WHERE e.id = $entity_id RETURN e LIMIT 1"
            existing = session.run(check_cypher, entity_id=entity_id).single()
            if not existing:
                return ToolResponse(
                    success=False,
                    error=f"Entity with id '{entity_id}' not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

        delete_cypher = "MATCH (e) WHERE e.id = $entity_id DETACH DELETE e"
        with writer._driver.session(database=writer.database) as session:
            session.run(delete_cypher, entity_id=entity_id)

        writer.log_operation(
            operation="DELETE_ENTITY",
            target_id=entity_id,
            target_type="Entity",
            user_id=agent_id,
            details="{}",
        )

        return ToolResponse(
            success=True,
            data={"entity_id": entity_id, "deleted": True},
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"kg_delete_entity failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def kg_create_relation(
    source_id: str,
    target_id: str,
    relation_type: str,
    properties: dict,
    agent_id: str,
    session_id: str,
) -> ToolResponse:
    """Create relation in knowledge graph"""
    operation_id = str(uuid.uuid4())
    try:
        from app.kg.src.storage.neo4j_writer import Neo4jWriter

        writer = Neo4jWriter()

        with writer._driver.session(database=writer.database) as session:
            source_check = session.run(
                "MATCH (s) WHERE s.id = $source_id RETURN s LIMIT 1",
                source_id=source_id
            ).single()
            if not source_check:
                return ToolResponse(
                    success=False,
                    error=f"Source entity with id '{source_id}' not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

            target_check = session.run(
                "MATCH (t) WHERE t.id = $target_id RETURN t LIMIT 1",
                target_id=target_id
            ).single()
            if not target_check:
                return ToolResponse(
                    success=False,
                    error=f"Target entity with id '{target_id}' not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

        relation_id = str(uuid.uuid4())
        rel_properties = {"id": relation_id, "relation_type": relation_type, **properties}
        prop_str = ", ".join([f"r.{k} = ${k}" for k in rel_properties.keys()])
        params = {"source_id": source_id, "target_id": target_id, **rel_properties}
        create_cypher = f"""
        MATCH (s), (t)
        WHERE s.id = $source_id AND t.id = $target_id
        CREATE (s)-[r:{relation_type} {{{prop_str}}}]->(t)
        RETURN r
        """

        with writer._driver.session(database=writer.database) as session:
            session.run(create_cypher, **params)

        writer.log_operation(
            operation="CREATE_RELATION",
            target_id=relation_id,
            target_type="Relation",
            user_id=agent_id,
            details=f"{{\"source\": \"{source_id}\", \"target\": \"{target_id}\", \"type\": \"{relation_type}\"}}",
        )

        return ToolResponse(
            success=True,
            data={
                "relation_id": relation_id,
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "properties": properties,
            },
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"kg_create_relation failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )


async def kg_delete_relation(
    source_id: str,
    target_id: str,
    relation_type: str,
    agent_id: str,
    session_id: str,
) -> ToolResponse:
    """Delete relation from knowledge graph"""
    operation_id = str(uuid.uuid4())
    try:
        from app.kg.src.storage.neo4j_writer import Neo4jWriter

        writer = Neo4jWriter()

        with writer._driver.session(database=writer.database) as session:
            check_cypher = f"""
            MATCH (s)-[r:{relation_type}]->(t)
            WHERE s.id = $source_id AND t.id = $target_id
            RETURN r LIMIT 1
            """
            existing = session.run(
                check_cypher,
                source_id=source_id,
                target_id=target_id
            ).single()
            if not existing:
                return ToolResponse(
                    success=False,
                    error=f"Relation of type '{relation_type}' between source '{source_id}' and target '{target_id}' not found",
                    operation_id=operation_id,
                    timestamp=datetime.utcnow(),
                )

        delete_cypher = f"""
        MATCH (s)-[r:{relation_type}]->(t)
        WHERE s.id = $source_id AND t.id = $target_id
        DELETE r
        """
        with writer._driver.session(database=writer.database) as session:
            session.run(delete_cypher, source_id=source_id, target_id=target_id)

        writer.log_operation(
            operation="DELETE_RELATION",
            target_id=f"{source_id}_{relation_type}_{target_id}",
            target_type="Relation",
            user_id=agent_id,
            details=f"{{\"source\": \"{source_id}\", \"target\": \"{target_id}\", \"type\": \"{relation_type}\"}}",
        )

        return ToolResponse(
            success=True,
            data={
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "deleted": True,
            },
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"kg_delete_relation failed: {e}")
        return ToolResponse(
            success=False,
            error=str(e),
            operation_id=operation_id,
            timestamp=datetime.utcnow(),
        )
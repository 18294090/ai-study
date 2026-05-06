"""Map relations tool for Hermes."""

from typing import Dict, Any, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


def map_relations(
    source_entity_id: str,
    target_entity_id: str,
    relation_type: str,
    properties: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a relation between two entities.

    Args:
        source_entity_id: Source entity ID
        target_entity_id: Target entity ID
        relation_type: Type of relation (e.g., "包含", "属于", "因果")
        properties: Optional relation properties

    Returns:
        Dict with relation_id and success status
    """
    try:
        from app.kg.src.storage.neo4j_writer import Neo4jWriter

        writer = Neo4jWriter()
        writer.init_schema()

        properties = properties or {}
        relation_id = str(uuid.uuid4())

        cypher = f"""
        MATCH (source), (target)
        WHERE source.id = $source_id AND target.id = $target_id
        CREATE (source)-[r:{relation_type} {{id: $relation_id, **$props}}]->(target)
        RETURN r
        """

        with writer._driver.session(database=writer.database) as session:
            result = session.run(
                cypher,
                source_id=source_entity_id,
                target_id=target_entity_id,
                relation_id=relation_id,
                props=properties
            )
            record = result.single()

        if record:
            writer.log_operation(
                operation="CREATE_RELATION",
                target_id=relation_id,
                target_type="Relation",
                user_id="hermes",
                details=f"{{\"source\": \"{source_entity_id}\", \"target\": \"{target_entity_id}\", \"type\": \"{relation_type}\"}}"
            )

            return {
                "success": True,
                "relation_id": relation_id,
                "source_id": source_entity_id,
                "target_id": target_entity_id,
                "relation_type": relation_type
            }
        else:
            return {"success": False, "error": "Failed to create relation"}

    except Exception as e:
        logger.error(f"map_relations failed: {e}")
        return {"success": False, "error": str(e)}
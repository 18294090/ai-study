"""Query graph tool for Hermes."""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def query_graph(
    query: str,
    query_type: str = "hybrid",
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Query the knowledge graph.

    Args:
        query: Query string (Cypher or semantic)
        query_type: Type of query (cypher, semantic, hybrid)
        filters: Optional filters

    Returns:
        Dict with results, paths, and intent
    """
    try:
        from app.kg.agents.graphrag_service import GraphRAGService

        service = GraphRAGService(neo4j_driver=None, qdrant_client=None)

        import asyncio
        result = asyncio.run(service.query(query))

        return {
            "success": True,
            "results": result.kg_paths or [],
            "intent": result.intent.value if hasattr(result.intent, 'value') else str(result.intent),
            "retrieval_type": result.retrieval_type
        }
    except Exception as e:
        logger.error(f"query_graph failed: {e}")
        return {"success": False, "error": str(e), "results": []}
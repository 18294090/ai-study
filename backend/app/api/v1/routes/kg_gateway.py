"""KG Gateway - FastAPI routes that proxy to Hermes via MCP."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


class ExtractRequest(BaseModel):
    source: str
    source_type: str = "text"
    subject_id: Optional[int] = None


class MapRelationRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    properties: Optional[dict] = None


class DetectConflictRequest(BaseModel):
    entity_id: str
    new_statement: str


class VerifyRequest(BaseModel):
    entity_ids: List[str]


@router.post("/entities/extract")
async def extract_entities(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user)
):
    """Extract entities from text or document via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("extract_entities", {
            "source": request.source,
            "source_type": request.source_type,
            "subject_id": request.subject_id
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relations/map")
async def map_relations(
    request: MapRelationRequest,
    current_user: User = Depends(get_current_user)
):
    """Map a relation between two entities via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("map_relations", {
            "source_entity_id": request.source_entity_id,
            "target_entity_id": request.target_entity_id,
            "relation_type": request.relation_type,
            "properties": request.properties or {}
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query")
async def query_graph(
    query: str = Query(..., description="Query string"),
    query_type: str = Query("hybrid", description="Query type: cypher, semantic, or hybrid"),
    current_user: User = Depends(get_current_user)
):
    """Query the knowledge graph via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("query_graph", {
            "query": query,
            "query_type": query_type,
            "filters": {}
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conflict/detect")
async def detect_conflict(
    request: DetectConflictRequest,
    current_user: User = Depends(get_current_user)
):
    """Detect conflicts for an entity via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("detect_conflict", {
            "entity_id": request.entity_id,
            "new_statement": request.new_statement
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
async def verify_knowledge(
    request: VerifyRequest,
    current_user: User = Depends(get_current_user)
):
    """Verify knowledge for entities via Hermes."""
    from app.mcp.hermes_client import get_hermes_client

    try:
        client = await get_hermes_client()
        result = await client.call_tool("verify_knowledge", {
            "entity_ids": request.entity_ids
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
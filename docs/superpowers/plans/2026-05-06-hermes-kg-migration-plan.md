# Hermes KG Migration Implementation Plan - Phase 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate KG Management to Hermes Agent kg_skill via MCP stdio transport

**Architecture:** FastAPI Gateway → HermesMCPClient (stdio) → Hermes Agent → KG Tools with Memory

**Tech Stack:** Hermes Agent (local), MCP Protocol (stdio), Neo4j, Qdrant

---

## File Structure

```
backend/app/
├── mcp/
│   ├── hermes_client.py      # NEW: MCP client for Hermes stdio
│   ├── kg_tools.py           # MODIFY: Keep existing, reference from hermes
│   └── __init__.py          # MODIFY: Export hermes client

hermes/
├── skills/
│   └── kg_skill.md           # NEW: KG skill definition
└── tools/kg_tools/           # NEW: Hermes KG tools
    ├── __init__.py
    ├── extract_entities.py
    ├── map_relations.py
    ├── query_graph.py
    ├── detect_conflict.py
    └── verify_knowledge.py

backend/app/api/v1/routes/
└── kg_gateway.py            # NEW: FastAPI KG gateway routes
```

---

## Task 1: Create Hermes MCP Client (stdio transport)

**Files:**
- Create: `backend/app/mcp/hermes_client.py`
- Modify: `backend/app/mcp/__init__.py`

- [ ] **Step 1: Write hermes_client.py**

```python
"""Hermes MCP Client for stdio transport."""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]


class HermesMCPClient:
    """MCP client for Hermes Agent communication via stdio."""

    def __init__(self, hermes_path: str = "hermes"):
        self.hermes_path = hermes_path
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id: int = 0
        self._running: bool = False

    async def start(self) -> bool:
        """Start Hermes process and initialize."""
        if self._running:
            return True

        try:
            self._process = await asyncio.create_subprocess_exec(
                self.hermes_path,
                "mcp",
                "start",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._running = True
            logger.info("Hermes MCP process started")
            return True
        except Exception as e:
            logger.error(f"Failed to start Hermes: {e}")
            return False

    async def stop(self):
        """Stop Hermes process."""
        if self._process and self._running:
            self._process.terminate()
            await self._process.wait()
            self._running = False
            logger.info("Hermes MCP process stopped")

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via MCP."""
        if not self._running:
            await self.start()

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        try:
            await self._process.stdin.send_str(json.dumps(request) + "\n")
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=30.0
            )
            response = json.loads(response_line)
            return response.get("result", {})
        except asyncio.TimeoutError:
            logger.error(f"Tool call {tool_name} timed out")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Tool call {tool_name} failed: {e}")
            return {"success": False, "error": str(e)}

    async def list_tools(self) -> List[MCPToolDefinition]:
        """List available tools from Hermes."""
        if not self._running:
            await self.start()

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }

        try:
            await self._process.stdin.send_str(json.dumps(request) + "\n")
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=10.0
            )
            response = json.loads(response_line)
            tools = response.get("result", {}).get("tools", [])
            return [MCPToolDefinition(**t) for t in tools]
        except Exception as e:
            logger.error(f"List tools failed: {e}")
            return []

    async def call_skill(self, skill_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Hermes skill."""
        if not self._running:
            await self.start()

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "skills/execute",
            "params": {
                "name": skill_name,
                "input": input_data
            }
        }

        try:
            await self._process.stdin.send_str(json.dumps(request) + "\n")
            response_line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=60.0
            )
            response = json.loads(response_line)
            return response.get("result", {})
        except asyncio.TimeoutError:
            logger.error(f"Skill {skill_name} timed out")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Skill {skill_name} failed: {e}")
            return {"success": False, "error": str(e)}


_client: Optional[HermesMCPClient] = None


async def get_hermes_client() -> HermesMCPClient:
    global _client
    if _client is None:
        _client = HermesMCPClient()
        await _client.start()
    return _client
```

- [ ] **Step 2: Modify __init__.py to export hermes_client**

```python
from .kg_tools import (
    kg_query,
    kg_create_entity,
    kg_update_entity,
    kg_delete_entity,
    kg_create_relation,
    kg_delete_relation,
)
from .hermes_client import HermesMCPClient, get_hermes_client

__all__ = [
    # kg_tools
    "kg_query",
    "kg_create_entity",
    "kg_update_entity",
    "kg_delete_entity",
    "kg_create_relation",
    "kg_delete_relation",
    # hermes client
    "HermesMCPClient",
    "get_hermes_client",
]
```

- [ ] **Step 3: Add tests**

```python
# tests/mcp/test_hermes_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_hermes_client_initialization():
    from backend.app.mcp.hermes_client import HermesMCPClient
    client = HermesMCPClient()
    assert client._request_id == 0
    assert client._running is False


@pytest.mark.asyncio
async def test_next_id_increments():
    from backend.app.mcp.hermes_client import HermesMCPClient
    client = HermesMCPClient()
    assert client._next_id() == 1
    assert client._next_id() == 2
    assert client._next_id() == 3


def test_mcp_tool_definition():
    from backend.app.mcp.hermes_client import MCPToolDefinition
    tool = MCPToolDefinition(
        name="test_tool",
        description="Test tool",
        input_schema={"type": "object"}
    )
    assert tool.name == "test_tool"
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=backend python3 -m pytest tests/mcp/test_hermes_client.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/mcp/hermes_client.py backend/app/mcp/__init__.py
git add tests/mcp/test_hermes_client.py
git commit -m "feat(mcp): add Hermes MCP client for stdio transport"
```

---

## Task 2: Create Hermes KG Skill Definition

**Files:**
- Create: `hermes/skills/kg_skill.md`

- [ ] **Step 1: Write kg_skill.md**

```markdown
# KG (Knowledge Graph) Skill

## Purpose
Manage knowledge graph construction, querying, and verification using Hermes Agent tools.

## Capabilities
- Extract entities from text/pdf/markdown documents
- Map relations between entities
- Query graph with Cypher, semantic, or hybrid search
- Detect knowledge conflicts
- Verify knowledge correctness

## Tools

### extract_entities
Extract knowledge graph entities from source text or documents.
- Input: source (str), source_type (text|pdf|markdown), subject_id (int, optional)
- Output: entities[], confidence (float)

### map_relations
Create relationships between entities.
- Input: source_entity_id, target_entity_id, relation_type, properties
- Output: relation_id, success

### query_graph
Query the knowledge graph using various methods.
- Input: query (str), query_type (cypher|semantic|hybrid), filters
- Output: results[], paths[], intent

### detect_conflict
Detect conflicts in knowledge graph.
- Input: entity_id, new_statement
- Output: conflicts[], severity

### verify_knowledge
Verify knowledge correctness in the graph.
- Input: entity_ids[]
- Output: verified[], issues[]

## Memory Integration
This skill uses Hermes's persistent memory to:
- Store KG operation history across sessions
- Remember entity disambiguation decisions
- Track relation mapping context
- Maintain verification history

## Configuration
- Neo4j: bolt://localhost:7687, database: neo4j
- Qdrant: http://localhost:6333, collection: textbook_chunks

## Quality Thresholds
- Entity extraction confidence: >= 0.7
- Relation mapping confidence: >= 0.6
- Conflict detection severity threshold: >= 0.5
```

- [ ] **Step 2: Create hermes/tools/kg_tools/ directory structure**

```bash
mkdir -p hermes/tools/kg_tools
touch hermes/tools/kg_tools/__init__.py
```

- [ ] **Step 3: Commit**

```bash
git add hermes/skills/kg_skill.md hermes/tools/kg_tools/__init__.py
git commit -m "feat(hermes): add kg_skill.md definition"
```

---

## Task 3: Create KG Tool Implementations for Hermes

**Files:**
- Create: `hermes/tools/kg_tools/extract_entities.py`
- Create: `hermes/tools/kg_tools/map_relations.py`
- Create: `hermes/tools/kg_tools/query_graph.py`
- Create: `hermes/tools/kg_tools/detect_conflict.py`
- Create: `hermes/tools/kg_tools/verify_knowledge.py`

- [ ] **Step 1: Write extract_entities.py**

```python
"""Extract entities tool for Hermes."""

from typing import Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    id: str
    name: str
    type: str
    properties: Dict[str, Any]
    confidence: float


def extract_entities(source: str, source_type: str = "text", subject_id: int = None) -> Dict[str, Any]:
    """Extract entities from source text or document.

    Args:
        source: Text content or file path
        source_type: Type of source (text, pdf, markdown)
        subject_id: Optional subject ID for context

    Returns:
        Dict with entities list and confidence score
    """
    try:
        from app.kg.src.llm_router import LLMRouter

        prompt = f"""从以下内容中提取知识图谱实体，返回JSON格式:

内容类型: {source_type}
内容: {source[:5000]}

返回格式:
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "properties": {{}}, "confidence": 0.0-1.0}}
    ],
    "confidence": 平均置信度
}}"""

        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)

        content = response.content if hasattr(response, 'content') else str(response)

        import json
        result = json.loads(content)

        return {
            "success": True,
            "entities": result.get("entities", []),
            "confidence": result.get("confidence", 0.0),
            "count": len(result.get("entities", []))
        }
    except Exception as e:
        logger.error(f"extract_entities failed: {e}")
        return {"success": False, "error": str(e), "entities": []}
```

- [ ] **Step 2: Write map_relations.py**

```python
"""Map relations tool for Hermes."""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def map_relations(
    source_entity_id: str,
    target_entity_id: str,
    relation_type: str,
    properties: Dict[str, Any] = None
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
        import uuid
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
```

- [ ] **Step 3: Write query_graph.py**

```python
"""Query graph tool for Hermes."""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def query_graph(
    query: str,
    query_type: str = "hybrid",
    filters: Dict[str, Any] = None
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
```

- [ ] **Step 4: Write detect_conflict.py**

```python
"""Detect conflict tool for Hermes."""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class Conflict:
    entity_id: str
    statement_a: str
    statement_b: str
    severity: float


def detect_conflict(entity_id: str, new_statement: str) -> Dict[str, Any]:
    """Detect conflicts for an entity.

    Args:
        entity_id: Entity ID to check
        new_statement: New statement to compare

    Returns:
        Dict with conflicts list and severity
    """
    try:
        from app.services.expert_reviewer_service import ConflictDetector

        detector = ConflictDetector()

        conflicts = detector.detect_conflicts(entity_id, new_statement)

        return {
            "success": True,
            "conflicts": [
                {
                    "entity_id": c.entity_id,
                    "statement_a": c.evidence.statement_a,
                    "statement_b": c.evidence.statement_b,
                    "severity": c.severity
                }
                for c in conflicts
            ],
            "conflict_count": len(conflicts),
            "has_conflicts": len(conflicts) > 0
        }
    except Exception as e:
        logger.error(f"detect_conflict failed: {e}")
        return {"success": False, "error": str(e), "conflicts": []}
```

- [ ] **Step 5: Write verify_knowledge.py**

```python
"""Verify knowledge tool for Hermes."""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def verify_knowledge(entity_ids: List[str]) -> Dict[str, Any]:
    """Verify knowledge correctness for entities.

    Args:
        entity_ids: List of entity IDs to verify

    Returns:
        Dict with verified entities and issues
    """
    try:
        from app.kg.agents.kg_linter import KGLinter

        linter = KGLinter()

        verified = []
        issues = []

        for entity_id in entity_ids:
            result = linter.verify_entity(entity_id)
            if result.get("valid"):
                verified.append(entity_id)
            else:
                issues.append({
                    "entity_id": entity_id,
                    "issues": result.get("issues", [])
                })

        return {
            "success": True,
            "verified": verified,
            "issues": issues,
            "verified_count": len(verified),
            "issue_count": len(issues)
        }
    except Exception as e:
        logger.error(f"verify_knowledge failed: {e}")
        return {"success": False, "error": str(e), "verified": [], "issues": []}
```

- [ ] **Step 6: Update __init__.py**

```python
from .extract_entities import extract_entities
from .map_relations import map_relations
from .query_graph import query_graph
from .detect_conflict import detect_conflict
from .verify_knowledge import verify_knowledge

__all__ = [
    "extract_entities",
    "map_relations",
    "query_graph",
    "detect_conflict",
    "verify_knowledge",
]
```

- [ ] **Step 7: Commit**

```bash
git add hermes/tools/kg_tools/extract_entities.py
git add hermes/tools/kg_tools/map_relations.py
git add hermes/tools/kg_tools/query_graph.py
git add hermes/tools/kg_tools/detect_conflict.py
git add hermes/tools/kg_tools/verify_knowledge.py
git add hermes/tools/kg_tools/__init__.py
git commit -m "feat(hermes): add KG tools for Hermes"
```

---

## Task 4: Create FastAPI KG Gateway Routes

**Files:**
- Create: `backend/app/api/v1/routes/kg_gateway.py`
- Modify: `backend/app/api/v1/__init__.py`

- [ ] **Step 1: Write kg_gateway.py**

```python
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
```

- [ ] **Step 2: Update api/v1/__init__.py**

Read the current file, then add:
```python
from .routes.kg_gateway import router as kg_gateway_router

# Add after other include_router calls:
api_v1_router.include_router(kg_gateway_router, prefix="/kg", tags=["knowledge-graph"])
```

- [ ] **Step 3: Add tests**

```python
# tests/api/v1/test_kg_gateway.py
import pytest
from unittest.mock import AsyncMock, patch


def test_kg_gateway_extract_request_model():
    from backend.app.api.v1.routes.kg_gateway import ExtractRequest
    req = ExtractRequest(source="test content", source_type="text")
    assert req.source == "test content"
    assert req.source_type == "text"


def test_kg_gateway_map_relation_request():
    from backend.app.api.v1.routes.kg_gateway import MapRelationRequest
    req = MapRelationRequest(
        source_entity_id="e1",
        target_entity_id="e2",
        relation_type="包含"
    )
    assert req.source_entity_id == "e1"
    assert req.relation_type == "包含"
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=backend python3 -m pytest tests/api/v1/test_kg_gateway.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/routes/kg_gateway.py
git add tests/api/v1/test_kg_gateway.py
git commit -m "feat(kg): add KG gateway routes for Hermes"
```

---

## Task 5: Integration Test and Verification

**Files:**
- Create: `tests/mcp/integration/test_hermes_kg_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration tests for Hermes KG MCP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_hermes_client_tool_call_flow():
    """Test the full flow of calling a Hermes tool."""
    from backend.app.mcp.hermes_client import HermesMCPClient

    client = HermesMCPClient()

    with patch.object(client, '_process') as mock_process:
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()

        mock_response = {"jsonrpc": "2.0", "id": 1, "result": {"success": True}}
        mock_process.stdout.readline = AsyncMock(return_value=json.dumps(mock_response))

        result = await client.call_tool("extract_entities", {"source": "test"})

        assert result.get("success") is True


def test_kg_gateway_routes_registered():
    """Test that KG gateway routes are registered."""
    from backend.app.api.v1 import api_v1_router

    route_paths = [route.path for route in api_v1_router.routes]
    assert any("/kg/entities/extract" in p for p in route_paths)
    assert any("/kg/relations/map" in p for p in route_paths)
    assert any("/kg/query" in p for p in route_paths)
    assert any("/kg/conflict/detect" in p for p in route_paths)
    assert any("/kg/verify" in p for p in route_paths)
```

- [ ] **Step 2: Run all KG tests**

Run: `PYTHONPATH=backend python3 -m pytest tests/mcp/ tests/api/v1/ -v --tb=short`

- [ ] **Step 3: Verify Hermes tools are defined**

Check that hermes/skills/kg_skill.md contains all 5 tools

- [ ] **Step 4: Commit**

```bash
git add tests/mcp/integration/test_hermes_kg_integration.py
git commit -m "test(kg): add Hermes KG integration tests"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - [x] extract_entities tool
   - [x] map_relations tool
   - [x] query_graph tool
   - [x] detect_conflict tool
   - [x] verify_knowledge tool
   - [x] HermesMCPClient (stdio transport)
   - [x] FastAPI KG gateway routes

2. **Placeholder scan:** No TBD/TODO found

3. **Type consistency:**
   - All tool names consistent (snake_case)
   - All request/response dict keys consistent

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/YYYY-MM-DD-hermes-kg-migration.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
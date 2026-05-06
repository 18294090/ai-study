"""Integration tests for Hermes KG MCP."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


@pytest.mark.asyncio
async def test_hermes_client_tool_call_flow():
    """Test the full flow of calling a Hermes tool."""
    from backend.app.mcp.hermes_client import HermesMCPClient

    client = HermesMCPClient()
    client._running = True

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


def test_kg_skill_tools_defined():
    """Test that all 5 KG tools are defined."""
    import os
    skill_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..",
        "hermes", "skills", "kg_skill.md"
    )
    assert os.path.exists(skill_path), f"kg_skill.md not found at {skill_path}"

    with open(skill_path) as f:
        content = f.read()

    for tool in ["extract_entities", "map_relations", "query_graph", "detect_conflict", "verify_knowledge"]:
        assert tool in content, f"{tool} not found in kg_skill.md"

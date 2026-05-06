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
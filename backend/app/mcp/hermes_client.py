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
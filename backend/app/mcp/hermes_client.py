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
            asyncio.create_task(self._consume_stderr())
            self._running = True
            logger.info("Hermes MCP process started")
            return await self._health_check()
        except Exception as e:
            logger.error(f"Failed to start Hermes: {e}")
            return False

    async def _consume_stderr(self):
        """Read stderr asynchronously to prevent deadlock."""
        if self._process and self._process.stderr:
            while True:
                try:
                    line = await self._process.stderr.readline()
                    if not line:
                        break
                    logger.warning(f"Hermes stderr: {line.decode().strip()}")
                except Exception:
                    break

    async def _health_check(self) -> bool:
        """Verify Hermes is ready by calling a simple method."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        try:
            await self._process.stdin.send_str(json.dumps(request) + "\n")
            await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=10.0
            )
            return True
        except Exception:
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

    async def __aenter__(self) -> "HermesMCPClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
        return False

    def _parse_response(self, response_line: str) -> Dict[str, Any]:
        """Parse JSON-RPC response and handle errors."""
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON: {e}"}

        if "error" in response:
            return {"success": False, "error": response["error"].get("message", "Unknown error")}
        return {"success": True, "result": response.get("result", {})}

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via MCP."""
        if not self._running:
            success = await self.start()
            if not success:
                return {"success": False, "error": "Failed to start Hermes"}

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
            result = self._parse_response(response_line)
            if result.get("success"):
                return {"success": True, "result": result.get("result", {})}
            return result
        except asyncio.TimeoutError:
            logger.error(f"Tool call {tool_name} timed out")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Tool call {tool_name} failed: {e}")
            return {"success": False, "error": str(e)}

    async def list_tools(self) -> List[MCPToolDefinition]:
        """List available tools from Hermes."""
        if not self._running:
            success = await self.start()
            if not success:
                return []

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
            result = self._parse_response(response_line)
            if not result.get("success"):
                logger.error(f"List tools failed: {result.get('error')}")
                return []
            tools = result.get("result", {}).get("tools", [])
            return [MCPToolDefinition(**t) for t in tools]
        except Exception as e:
            logger.error(f"List tools failed: {e}")
            return []

    async def call_skill(self, skill_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Hermes skill."""
        if not self._running:
            success = await self.start()
            if not success:
                return {"success": False, "error": "Failed to start Hermes"}

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
            result = self._parse_response(response_line)
            if result.get("success"):
                return {"success": True, "result": result.get("result", {})}
            return result
        except asyncio.TimeoutError:
            logger.error(f"Skill {skill_name} timed out")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Skill {skill_name} failed: {e}")
            return {"success": False, "error": str(e)}


_client: Optional[HermesMCPClient] = None
_lock: asyncio.Lock = asyncio.Lock()


async def get_hermes_client() -> HermesMCPClient:
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                _client = HermesMCPClient()
                await _client.start()
    return _client
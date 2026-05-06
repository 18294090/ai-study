#!/usr/bin/env python3
"""MCP Server wrapper for kg_tools and tutor_tools.

This wraps our Python tools as an MCP server that Hermes can call via stdio.
"""

import json
import sys
import os

# Add project root and backend to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend'))

from hermes.tools.kg_tools import (
    extract_entities,
    map_relations,
    query_graph,
    detect_conflict,
    verify_knowledge,
)
from hermes.tools.tutor_tools import (
    tutor_start,
    tutor_respond,
    tutor_get_state,
    tutor_end,
)


TOOL_HANDLERS = {
    "extract_entities": extract_entities,
    "map_relations": map_relations,
    "query_graph": query_graph,
    "detect_conflict": detect_conflict,
    "verify_knowledge": verify_knowledge,
    "tutor_start": tutor_start,
    "tutor_respond": tutor_respond,
    "tutor_get_state": tutor_get_state,
    "tutor_end": tutor_end,
}


def handle_request(request):
    """Handle incoming JSON-RPC request."""
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "kg-tutor-server", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        tools = []
        for name, handler in TOOL_HANDLERS.items():
            doc = handler.__doc__ or ""
            first_line = doc.strip().split("\n")[0] if doc else name
            tools.append({
                "name": name,
                "description": first_line,
                "inputSchema": {"type": "object", "properties": {}},
            })
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

    elif method == "tools/call":
        params = request.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})

        if name not in TOOL_HANDLERS:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Unknown tool: {name}"},
            }

        try:
            handler = TOOL_HANDLERS[name]
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                result = asyncio.run(handler(**arguments))
            else:
                result = handler(**arguments)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": not result.get("success", True),
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps({"success": False, "error": str(e)})}],
                    "isError": True,
                },
            }

    elif method == "notifications/initialized":
        return None

    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def main():
    """Main loop - read requests from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)

            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {e}"},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()

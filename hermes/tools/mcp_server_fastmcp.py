#!/usr/bin/env python3
"""MCP Server using FastMCP for kg_tools and tutor_tools.

This server exposes our Python tools as MCP tools that Hermes can call.
Uses the official MCP Python SDK (FastMCP).
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'backend'))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("kg-tutor-server")

# Import kg_tools with aliases
from hermes.tools.kg_tools import (
    extract_entities as _extract_entities_impl,
    map_relations as _map_relations_impl,
    query_graph as _query_graph_impl,
    detect_conflict as _detect_conflict_impl,
    verify_knowledge as _verify_knowledge_impl,
)

# Import tutor_tools with aliases
from hermes.tools.tutor_tools import (
    tutor_start as _tutor_start_impl,
    tutor_respond as _tutor_respond_impl,
    tutor_get_state as _tutor_get_state_impl,
    tutor_end as _tutor_end_impl,
)


@mcp.tool()
def extract_entities(source: str, source_type: str = "text", subject_id: int = None):
    """Extract entities from source text or document."""
    return _extract_entities_impl(source=source, source_type=source_type, subject_id=subject_id)


@mcp.tool()
def map_relations(source_entity_id: str, target_entity_id: str, relation_type: str, properties: dict = None):
    """Create a relation between two entities."""
    return _map_relations_impl(source_entity_id=source_entity_id, target_entity_id=target_entity_id, relation_type=relation_type, properties=properties)


@mcp.tool()
def query_graph(query: str, query_type: str = "hybrid", filters: dict = None):
    """Query the knowledge graph."""
    return _query_graph_impl(query=query, query_type=query_type, filters=filters)


@mcp.tool()
def detect_conflict(entity_id: str, new_statement: str):
    """Detect conflicts for an entity."""
    return _detect_conflict_impl(entity_id=entity_id, new_statement=new_statement)


@mcp.tool()
def verify_knowledge(entity_ids: list):
    """Verify knowledge correctness for KG."""
    return _verify_knowledge_impl(entity_ids=entity_ids)


@mcp.tool()
def tutor_start(user_id: int, concept_id: str, p_know: float, conversation_history: list = None):
    """Start a new Socratic tutor session."""
    return _tutor_start_impl(user_id=user_id, concept_id=concept_id, p_know=p_know, conversation_history=conversation_history)


@mcp.tool()
def tutor_respond(session_id: str, student_message: str, role: str = "student"):
    """Process student message and generate tutor response."""
    return _tutor_respond_impl(session_id=session_id, student_message=student_message, role=role)


@mcp.tool()
def tutor_get_state(session_id: str):
    """Get current tutor session state."""
    return _tutor_get_state_impl(session_id=session_id)


@mcp.tool()
def tutor_end(session_id: str, summary: str = None):
    """End tutor session."""
    return _tutor_end_impl(session_id=session_id, summary=summary)


if __name__ == "__main__":
    mcp.run()

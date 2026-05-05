from fastapi_mcp import FastApiMCP
from app.mcp.kg_tools import (
    kg_query, kg_create_entity, kg_update_entity,
    kg_delete_entity, kg_create_relation, kg_delete_relation,
)
from app.mcp.mastery_tools import (
    mastery_diagnose, mastery_update, mastery_get,
)
from app.mcp.tutor_tools import (
    tutor_start_session, tutor_message, tutor_get_session,
)
from app.mcp.irt_tools import (
    irt_calibrate, irt_estimate_ability, irt_update_ability,
)
from app.mcp.fsrs_tools import (
    fsrs_create_card, fsrs_review, fsrs_get_due, fsrs_get_stats,
)
from app.mcp.expert_tools import (
    expert_get_conflicts, expert_resolve, expert_submit_review, expert_get_stats,
)
from app.mcp.undo_tools import undo, get_undo_stack

def register_mcp_tools(mcp_server: FastApiMCP):
    """Register all MCP tools with the server"""

    # KG tools
    mcp_server.add_tool(
        name="kg_query",
        description="Query knowledge graph for answers using GraphRAG",
        tool=kg_query,
    )
    mcp_server.add_tool(
        name="kg_create_entity",
        description="Create entity in knowledge graph",
        tool=kg_create_entity,
    )
    mcp_server.add_tool(
        name="kg_update_entity",
        description="Update entity in knowledge graph",
        tool=kg_update_entity,
    )
    mcp_server.add_tool(
        name="kg_delete_entity",
        description="Delete entity from knowledge graph",
        tool=kg_delete_entity,
    )
    mcp_server.add_tool(
        name="kg_create_relation",
        description="Create relation in knowledge graph",
        tool=kg_create_relation,
    )
    mcp_server.add_tool(
        name="kg_delete_relation",
        description="Delete relation from knowledge graph",
        tool=kg_delete_relation,
    )

    # Mastery tools
    mcp_server.add_tool(name="mastery_diagnose", description="Run BKT diagnostic", tool=mastery_diagnose)
    mcp_server.add_tool(name="mastery_update", description="Update BKT mastery", tool=mastery_update)
    mcp_server.add_tool(name="mastery_get", description="Get mastery state", tool=mastery_get)

    # Tutor tools
    mcp_server.add_tool(name="tutor_start_session", description="Start tutor session", tool=tutor_start_session)
    mcp_server.add_tool(name="tutor_message", description="Send tutor message", tool=tutor_message)
    mcp_server.add_tool(name="tutor_get_session", description="Get tutor session", tool=tutor_get_session)

    # IRT tools
    mcp_server.add_tool(name="irt_calibrate", description="Calibrate IRT items", tool=irt_calibrate)
    mcp_server.add_tool(name="irt_estimate_ability", description="Estimate ability", tool=irt_estimate_ability)
    mcp_server.add_tool(name="irt_update_ability", description="Update ability", tool=irt_update_ability)

    # FSRS tools
    mcp_server.add_tool(name="fsrs_create_card", description="Create FSRS card", tool=fsrs_create_card)
    mcp_server.add_tool(name="fsrs_review", description="Submit FSRS review", tool=fsrs_review)
    mcp_server.add_tool(name="fsrs_get_due", description="Get due cards", tool=fsrs_get_due)
    mcp_server.add_tool(name="fsrs_get_stats", description="Get FSRS stats", tool=fsrs_get_stats)

    # Expert tools
    mcp_server.add_tool(name="expert_get_conflicts", description="Get conflict queue", tool=expert_get_conflicts)
    mcp_server.add_tool(name="expert_resolve", description="Resolve conflict", tool=expert_resolve)
    mcp_server.add_tool(name="expert_submit_review", description="Submit review", tool=expert_submit_review)
    mcp_server.add_tool(name="expert_get_stats", description="Get expert stats", tool=expert_get_stats)

    # Undo tools
    mcp_server.add_tool(name="undo", description="Undo operations", tool=undo)
    mcp_server.add_tool(name="get_undo_stack", description="Get undo stack", tool=get_undo_stack)

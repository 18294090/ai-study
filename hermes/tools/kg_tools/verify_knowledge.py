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
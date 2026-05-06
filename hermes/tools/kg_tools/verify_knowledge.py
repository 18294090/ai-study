"""Verify knowledge tool for Hermes."""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def verify_knowledge(textbook_id: str = None) -> Dict[str, Any]:
    """Verify knowledge correctness for KG.

    Args:
        textbook_id: Optional textbook ID to verify (verifies all if None)

    Returns:
        Dict with KG health report
    """
    try:
        from app.kg.agents.kg_linter import KGLinter

        driver = None
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",
                auth=("neo4j", "password")
            )
        except Exception:
            pass

        if driver is None:
            return {
                "success": False,
                "error": "neo4j_driver not available",
                "verified": [],
                "issues": []
            }

        linter = KGLinter(neo4j_driver=driver)
        report = linter.check(textbook_id=textbook_id)

        return {
            "success": True,
            "verified_count": report.total_nodes,
            "issue_count": len(report.issues),
            "health_score": report.health_score,
            "issues": [
                {
                    "type": issue.type,
                    "node_id": issue.node_id,
                    "description": issue.description,
                    "severity": issue.severity
                }
                for issue in report.issues
            ]
        }
    except Exception as e:
        logger.error(f"verify_knowledge failed: {e}")
        return {"success": False, "error": str(e), "verified": [], "issues": []}
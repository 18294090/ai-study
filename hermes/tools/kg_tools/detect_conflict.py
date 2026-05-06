"""Detect conflict tool for Hermes."""

from typing import Dict, Any, List
from dataclasses import dataclass
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

        conflicts = detector.detect_conflicts(int(entity_id), new_statement)

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
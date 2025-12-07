"""Helper utilities for generating KnowledgePoint identifiers."""

from __future__ import annotations

import re
from unicodedata import normalize
from uuid import uuid4

_slug_pattern = re.compile(r"[^a-z0-9]+")


def generate_knowledge_point_code(subject_id: int) -> str:
    """Generate a unique, human-friendly code for a knowledge point."""
    return f"KP-{subject_id}-{uuid4().hex[:8].upper()}"


def generate_knowledge_point_slug(name: str, subject_id: int) -> str:
    """Generate a URL-friendly slug derived from the knowledge point name."""
    normalized = normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    base = _slug_pattern.sub("-", normalized).strip("-")
    if not base:
        base = f"kp-{subject_id}"
    return f"{base}-{uuid4().hex[:6]}"


__all__ = [
    "generate_knowledge_point_code",
    "generate_knowledge_point_slug",
]

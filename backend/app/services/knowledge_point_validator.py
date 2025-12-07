"""Validation helpers for KnowledgePoint lifecycle operations."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint


async def ensure_unique_name(
    db: AsyncSession,
    subject_id: int,
    name: str,
    exclude_id: Optional[int] = None,
) -> None:
    """Ensure that a subject does not contain duplicate knowledge point names."""
    normalized_name = name.strip().lower()
    stmt = (
        select(KnowledgePoint.id)
        .where(
            KnowledgePoint.subject_id == subject_id,
            func.lower(KnowledgePoint.name) == normalized_name,
        )
        .limit(1)
    )
    if exclude_id is not None:
        stmt = stmt.where(KnowledgePoint.id != exclude_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise ValueError("名称已存在，请勿重复创建")


async def validate_creation(db: AsyncSession, subject_id: int, name: str) -> None:
    """Run all validations needed before creating a knowledge point."""
    await ensure_unique_name(db, subject_id, name)


async def validate_update(
    db: AsyncSession,
    subject_id: int,
    name: Optional[str],
    knowledge_point_id: int,
) -> None:
    """Validate updates (currently only uniqueness when name changes)."""
    if name is None:
        return
    await ensure_unique_name(db, subject_id, name, exclude_id=knowledge_point_id)


__all__ = [
    "validate_creation",
    "validate_update",
]

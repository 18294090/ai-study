"""Permission helpers for decentralized system.

In a decentralized AI learning system, all users (USER role) have equal
capabilities. Permissions are simplified to just authentication checks.
"""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User


def require_auth():
    """Require user to be authenticated."""
    async def dependency(current_user: User = Depends(get_current_user)):
        return current_user
    return Depends(dependency)
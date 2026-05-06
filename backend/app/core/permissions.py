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


async def check_subject_member(subject_id: int, current_user: User, db: AsyncSession) -> None:
    """Compatibility check used by subject-scoped routes.

    In the current decentralized model, authenticated users are allowed to
    access subject data. Keep this helper so existing routes can reuse a
    stable permission API.
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if subject_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid subject id")
    # No membership restriction in decentralized mode.
    return None
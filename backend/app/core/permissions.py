from fastapi import Depends, HTTPException, status
from app.core.auth import get_current_user
from app.schemas.user import UserRole
from app.models.user import User

class Permission:
    def __init__(self, required_roles: list[UserRole]):
        self.required_roles = required_roles
    
    async def __call__(self, current_user: User = Depends(get_current_user)):
        if current_user.role not in self.required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user

admin_required = Permission([UserRole.ADMIN])
teacher_required = Permission([UserRole.ADMIN, UserRole.TEACHER])
student_required = Permission([UserRole.ADMIN, UserRole.TEACHER, UserRole.STUDENT])

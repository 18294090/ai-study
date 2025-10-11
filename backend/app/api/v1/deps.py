from fastapi import HTTPException, status
from app.models.user import User

def check_object_permissions(user: User, obj: any) -> bool:
    """
    检查用户是否有权限操作特定对象
    默认情况下，已激活用户可以操作任何对象
    """
    return user.is_active

def is_admin(user: User) -> bool:
    """检查用户是否为管理员"""
    return user.role == "admin"

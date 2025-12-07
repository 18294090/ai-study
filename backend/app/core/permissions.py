from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user
from app.db.session import get_db
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

# 角色-based权限
admin_required = Permission([UserRole.ADMIN])
user_required = Permission([UserRole.USER, UserRole.ADMIN])

# 所有权和成员关系检查函数
async def check_subject_owner(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """检查并返回学科所有者权限的用户"""
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")

    if subject.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有学科创建者才能执行此操作")

    return current_user

async def check_subject_member(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """检查并返回学科成员权限的用户（所有者或已加入成员）"""
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")

    # 所有者自动是成员
    if subject.user_id == current_user.id:
        return current_user

    # 检查是否是已批准的成员
    # 这里需要检查user_subject关联表
    from sqlalchemy import select
    from app.models.subject import user_subject

    query = select(user_subject).where(
        user_subject.c.user_id == current_user.id,
        user_subject.c.subject_id == subject_id
    )
    result = await db.execute(query)
    if result.first():
        return current_user

    raise HTTPException(status_code=403, detail="您不是该学科的成员")

async def check_class_owner(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """检查并返回班级所有者权限的用户"""
    from app.models.class_model import Class
    class_obj = await db.get(Class, class_id)
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    if class_obj.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有班级创建者才能执行此操作")

    return current_user

async def check_class_member(
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """检查并返回班级成员权限的用户（所有者或已加入成员）"""
    from app.models.class_model import Class
    class_obj = await db.get(Class, class_id)
    if not class_obj:
        raise HTTPException(status_code=404, detail="班级不存在")

    # 所有者自动是成员
    if class_obj.teacher_id == current_user.id:
        return current_user

    # 检查是否是已批准的成员
    from sqlalchemy import select
    from app.models.class_model import class_student

    query = select(class_student).where(
        class_student.c.student_id == current_user.id,
        class_student.c.class_id == class_id
    )
    result = await db.execute(query)
    if result.first():
        return current_user

    raise HTTPException(status_code=403, detail="您不是该班级的成员")

# 便捷权限装饰器
def require_subject_owner():
    """要求用户是学科的所有者"""
    async def dependency(
        subject_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        return await check_subject_owner(subject_id, current_user, db)
    return Depends(dependency)

def require_subject_member():
    """要求用户是学科的成员"""
    async def dependency(
        subject_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        return await check_subject_member(subject_id, current_user, db)
    return Depends(dependency)

def require_class_owner():
    """要求用户是班级的所有者"""
    async def dependency(
        class_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        return await check_class_owner(class_id, current_user, db)
    return Depends(dependency)

def require_class_member():
    """要求用户是班级的成员"""
    async def dependency(
        class_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        return await check_class_member(class_id, current_user, db)
    return Depends(dependency)

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User

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
    """任何登录用户都可以加入/参与学科"""
    from app.models.subject import Subject
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")

    if subject.user_id == current_user.id:
        return current_user

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

    if class_obj.teacher_id == current_user.id:
        return current_user

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

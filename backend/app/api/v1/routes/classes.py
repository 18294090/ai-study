from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from app.db.session import get_db
from app.models.class_model import Class
from app.schemas.class_schema import ClassCreate, ClassUpdate, ClassResponse, ClassDetailResponse
from app.core.auth import get_current_user
from app.models.user import User
from app.core.permissions import check_class_owner, check_class_member

router = APIRouter()

@router.post("/", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建班级"""
    db_class = Class(
        **class_data.dict(),
        teacher_id=current_user.id
    )
    db.add(db_class)
    await db.commit()
    await db.refresh(db_class)
    return db_class

@router.get("/", response_model=List[ClassResponse])
async def get_classes(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户相关的所有班级（创建的或加入的）"""
    # 获取用户创建的班级
    owned_query = select(Class).where(Class.teacher_id == current_user.id)
    owned_result = await db.execute(owned_query)
    owned_classes = owned_result.scalars().all()

    # 获取用户加入的班级
    from app.models.class_model import class_student
    joined_query = select(Class).join(
        class_student,
        Class.id == class_student.c.class_id
    ).where(class_student.c.student_id == current_user.id)
    joined_result = await db.execute(joined_query)
    joined_classes = joined_result.scalars().all()

    # 合并并去重
    all_classes = list(owned_classes) + list(joined_classes)
    unique_classes = []
    seen_ids = set()
    for cls in all_classes:
        if cls.id not in seen_ids:
            seen_ids.add(cls.id)
            unique_classes.append(cls)

    return unique_classes[skip:skip + limit]

@router.get("/{class_id}", response_model=ClassDetailResponse)
async def get_class(
    class_id: int = Path(..., description="班级ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取班级详情"""
    # 检查用户是否是班级成员（所有者或已加入成员）
    await check_class_member(class_id, current_user, db)

    query = select(Class).where(Class.id == class_id)
    result = await db.execute(query)
    class_obj = result.scalar_one_or_none()

    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )

    # 获取学生数量
    from app.models.class_model import class_student
    count_query = select(func.count()).select_from(class_student).where(
        class_student.c.class_id == class_id
    )
    students_count = await db.scalar(count_query) or 0

    # 构建响应
    return {
        **class_obj.__dict__,
        "students_count": students_count
    }

@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_update: ClassUpdate,
    class_id: int = Path(..., description="班级ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新班级（仅班级所有者可操作）"""
    # 检查用户是否是班级所有者
    await check_class_owner(class_id, current_user, db)

    query = select(Class).where(Class.id == class_id)
    result = await db.execute(query)
    db_class = result.scalar_one_or_none()

    if not db_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )

    # 更新班级
    for key, value in class_update.dict(exclude_unset=True).items():
        setattr(db_class, key, value)

    await db.commit()
    await db.refresh(db_class)
    return db_class

@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: int = Path(..., description="班级ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除班级（仅班级所有者可操作）"""
    # 检查用户是否是班级所有者
    await check_class_owner(class_id, current_user, db)

    query = select(Class).where(Class.id == class_id)
    result = await db.execute(query)
    db_class = result.scalar_one_or_none()

    if not db_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="班级不存在"
        )

    # 删除班级
    await db.delete(db_class)
    await db.commit()

@router.get("/{class_id}/students", response_model=List[dict])
async def get_class_students(
    class_id: int = Path(..., description="班级ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取班级学生列表（仅班级成员可见）"""
    # 检查用户是否是班级成员
    await check_class_member(class_id, current_user, db)

    from app.models.class_model import class_student
    from app.models.user import User

    query = select(User).join(
        class_student,
        User.id == class_student.c.student_id
    ).where(class_student.c.class_id == class_id)

    result = await db.execute(query)
    students = result.scalars().all()

    return [{"id": student.id, "username": student.username, "email": student.email} for student in students]
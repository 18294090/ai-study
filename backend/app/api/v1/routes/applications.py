from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.application import ApplicationStatus
from app.schemas.application import (
    SubjectApplication, SubjectApplicationCreate, SubjectApplicationUpdate,
    ClassApplication, ClassApplicationCreate, ClassApplicationUpdate
)
from app.crud.application import crud_application
from app.core.permissions import check_subject_owner, check_class_owner

router = APIRouter()

# 学科申请路由
@router.post("/subjects/{subject_id}/applications", response_model=SubjectApplication)
async def create_subject_application(
    subject_id: int,
    application_in: SubjectApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """申请加入学科"""
    # 检查是否已经是成员
    from app.models.subject import user_subject
    from sqlalchemy import select

    query = select(user_subject).where(
        user_subject.c.user_id == current_user.id,
        user_subject.c.subject_id == subject_id
    )
    result = await db.execute(query)
    if result.first():
        raise HTTPException(status_code=400, detail="您已经是该学科的成员")

    # 检查是否已有待处理的申请
    existing_apps = await crud_application.get_subject_applications_by_subject(
        db, subject_id=subject_id, status=ApplicationStatus.PENDING
    )
    for app in existing_apps:
        if app.applicant_id == current_user.id:
            raise HTTPException(status_code=400, detail="您已有待处理的申请")

    application_in.subject_id = subject_id
    application_in.applicant_id = current_user.id
    return await crud_application.create_subject_application(db, obj_in=application_in)

@router.get("/subjects/{subject_id}/applications", response_model=List[SubjectApplication])
async def get_subject_applications(
    subject_id: int,
    status: Optional[ApplicationStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取学科的所有申请（仅学科所有者可见）"""
    # 检查权限：只有学科所有者可以查看申请
    await check_subject_owner(subject_id, current_user, db)

    return await crud_application.get_subject_applications_by_subject(
        db, subject_id=subject_id, status=status
    )

@router.put("/subjects/applications/{application_id}", response_model=SubjectApplication)
async def update_subject_application(
    application_id: int,
    application_update: SubjectApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批准或拒绝学科申请（仅学科所有者可操作）"""
    application = await crud_application.get_subject_application(db, id=application_id)
    if not application:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 验证权限：只有学科所有者可以处理申请
    await check_subject_owner(application.subject_id, current_user, db)

    updated_app = await crud_application.update_subject_application(
        db, id=application_id, obj_in=application_update
    )

    # 如果批准申请，自动添加用户到学科成员
    if application_update.status == ApplicationStatus.APPROVED:
        from app.models.subject import user_subject
        from sqlalchemy import insert, select

        # 检查是否已经添加
        query = select(user_subject).where(
            user_subject.c.user_id == application.applicant_id,
            user_subject.c.subject_id == application.subject_id
        )
        result = await db.execute(query)
        if not result.first():
            await db.execute(insert(user_subject).values(
                user_id=application.applicant_id,
                subject_id=application.subject_id
            ))
            await db.commit()

    return updated_app

@router.delete("/subjects/applications/{application_id}")
async def delete_subject_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除学科申请（申请者或学科所有者可操作）"""
    application = await crud_application.get_subject_application(db, id=application_id)
    if not application:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 只有申请者或学科所有者可以删除
    if (application.applicant_id != current_user.id and
        application.subject.user_id != current_user.id):
        raise HTTPException(status_code=403, detail="无权删除此申请")

    success = await crud_application.delete_subject_application(db, id=application_id)
    if not success:
        raise HTTPException(status_code=404, detail="申请不存在")
    return {"message": "申请已删除"}

# 班级申请路由
@router.post("/classes/{class_id}/applications", response_model=ClassApplication)
async def create_class_application(
    class_id: int,
    application_in: ClassApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """申请加入班级"""
    # 检查是否已经是成员
    from app.models.class_model import class_student
    from sqlalchemy import select

    query = select(class_student).where(
        class_student.c.student_id == current_user.id,
        class_student.c.class_id == class_id
    )
    result = await db.execute(query)
    if result.first():
        raise HTTPException(status_code=400, detail="您已经是该班级的成员")

    # 检查是否已有待处理的申请
    existing_apps = await crud_application.get_class_applications_by_class(
        db, class_id=class_id, status=ApplicationStatus.PENDING
    )
    for app in existing_apps:
        if app.applicant_id == current_user.id:
            raise HTTPException(status_code=400, detail="您已有待处理的申请")

    application_in.class_id = class_id
    application_in.applicant_id = current_user.id
    return await crud_application.create_class_application(db, obj_in=application_in)

@router.get("/classes/{class_id}/applications", response_model=List[ClassApplication])
async def get_class_applications(
    class_id: int,
    status: Optional[ApplicationStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取班级的所有申请（仅班级所有者可见）"""
    # 检查权限：只有班级所有者可以查看申请
    await check_class_owner(class_id, current_user, db)

    return await crud_application.get_class_applications_by_class(
        db, class_id=class_id, status=status
    )

@router.put("/classes/applications/{application_id}", response_model=ClassApplication)
async def update_class_application(
    application_id: int,
    application_update: ClassApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批准或拒绝班级申请（仅班级所有者可操作）"""
    application = await crud_application.get_class_application(db, id=application_id)
    if not application:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 验证权限：只有班级所有者可以处理申请
    await check_class_owner(application.class_id, current_user, db)

    updated_app = await crud_application.update_class_application(
        db, id=application_id, obj_in=application_update
    )

    # 如果批准申请，自动添加用户到班级成员
    if application_update.status == ApplicationStatus.APPROVED:
        from app.models.class_model import class_student
        from sqlalchemy import insert, select

        # 检查是否已经添加
        query = select(class_student).where(
            class_student.c.student_id == application.applicant_id,
            class_student.c.class_id == application.class_id
        )
        result = await db.execute(query)
        if not result.first():
            await db.execute(insert(class_student).values(
                student_id=application.applicant_id,
                class_id=application.class_id
            ))
            await db.commit()

    return updated_app

@router.delete("/classes/applications/{application_id}")
async def delete_class_application(
    application_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除班级申请（申请者或班级所有者可操作）"""
    application = await crud_application.get_class_application(db, id=application_id)
    if not application:
        raise HTTPException(status_code=404, detail="申请不存在")

    # 只有申请者或班级所有者可以删除
    if (application.applicant_id != current_user.id and
        application.class_.teacher_id != current_user.id):
        raise HTTPException(status_code=403, detail="无权删除此申请")

    success = await crud_application.delete_class_application(db, id=application_id)
    if not success:
        raise HTTPException(status_code=404, detail="申请不存在")
    return {"message": "申请已删除"}

# 用户申请记录路由
@router.get("/my-applications", response_model=List[SubjectApplication | ClassApplication])
async def get_my_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的所有申请记录"""
    return await crud_application.get_applications_by_applicant(db, applicant_id=current_user.id)
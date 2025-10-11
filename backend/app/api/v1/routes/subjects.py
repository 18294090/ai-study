from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from app.db.session import get_db
from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate, SubjectResponse, SubjectDetailResponse
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建学科"""
    db_subject = Subject(
        **subject.dict(),
        user_id=current_user.id
    )
    db.add(db_subject)
    await db.commit()
    await db.refresh(db_subject)
    return db_subject

@router.get("/", response_model=List[SubjectResponse])
async def get_subjects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有学科"""
    query = select(
        Subject,
        func.count(KnowledgePoint.id).label("knowledge_points_count")
    ).outerjoin(
        KnowledgePoint,
        Subject.id == KnowledgePoint.subject_id
    ).where(Subject.user_id == current_user.id).group_by(
        Subject.id
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    
    subjects = []
    for subject, knowledge_points_count in result:
        subject_dict = {
            **subject.__dict__,
            "knowledge_points_count": knowledge_points_count
        }
        subjects.append(subject_dict)
    
    return subjects

@router.get("/{subject_id}", response_model=SubjectDetailResponse)
async def get_subject(
    subject_id: int = Path(..., description="学科ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取学科详情"""
    query = select(Subject).where(
        Subject.id == subject_id,
        Subject.user_id == current_user.id
    )
    result = await db.execute(query)
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学科不存在或您没有权限访问"
        )
    
    # 获取知识点数量
    count_query = select(func.count()).where(KnowledgePoint.subject_id == subject_id)
    knowledge_points_count = await db.scalar(count_query) or 0
    
    # 构建响应
    return {
        **subject.__dict__,
        "knowledge_points_count": knowledge_points_count
    }

@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: int = Path(..., description="学科ID"),
    subject_update: Optional[SubjectUpdate] = None,  # 添加默认值 None
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新学科"""
    if subject_update is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请求体不能为空"
        )
    
    query = select(Subject).where(
        Subject.id == subject_id,
        Subject.user_id == current_user.id
    )
    result = await db.execute(query)
    db_subject = result.scalar_one_or_none()
    
    if not db_subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学科不存在或您没有权限访问"
        )
    
    # 更新学科
    for key, value in subject_update.dict(exclude_unset=True).items():
        setattr(db_subject, key, value)
    
    await db.commit()
    await db.refresh(db_subject)
    return db_subject

@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: int = Path(..., description="学科ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除学科"""
    query = select(Subject).where(
        Subject.id == subject_id,
        Subject.user_id == current_user.id
    )
    result = await db.execute(query)
    db_subject = result.scalar_one_or_none()
    
    if not db_subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学科不存在或您没有权限访问"
        )
    
    # 删除学科
    await db.delete(db_subject)
    await db.commit()

@router.get("/{subject_id}/recommendations")
async def get_subject_recommendations(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取学科学习建议"""
    # 验证学科属于当前用户
    subject_query = select(Subject).where(
        Subject.id == subject_id,
        Subject.user_id == current_user.id
    )
    subject_result = await db.execute(subject_query)
    subject = subject_result.scalar_one_or_none()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学科不存在或您没有权限访问"
        )    
    # 分析用户薄弱知识点
    weak_points = await analyze_weak_points(subject_id, current_user.id, db)
    # 生成学习建议
    recommendations = await generate_learning_recommendations(
        subject_id, 
        current_user.id,
        weak_points,
        db
    )
    return recommendations


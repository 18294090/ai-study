from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.subject import Subject
from app.models.knowledge import KnowledgePoint

router = APIRouter(prefix="/subjects", tags=["subjects"])


class SubjectResponse(BaseModel):
    id: int
    name: str
    grade_level: Optional[str]
    description: Optional[str]
    knowledge_points_count: int = 0

    class Config:
        from_attributes = True


class SubjectListResponse(BaseModel):
    subjects: List[SubjectResponse]
    total: int


@router.get("/", response_model=List[SubjectResponse])
async def list_subjects(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """获取所有学科列表"""
    query = select(
        Subject,
        func.count(KnowledgePoint.id).label("kp_count")
    ).outerjoin(
        KnowledgePoint,
        Subject.id == KnowledgePoint.subject_id
    ).group_by(Subject.id).offset(skip).limit(limit)

    result = await db.execute(query)
    return [
        SubjectResponse(
            id=s.id,
            name=s.name,
            grade_level=s.grade_level,
            description=s.description,
            knowledge_points_count=kp_count
        )
        for s, kp_count in result
    ]


@router.get("/search")
async def search_subjects(
    q: str = Query(..., min_length=1),
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """搜索学科"""
    query = select(Subject).where(
        Subject.name.contains(q)
    ).limit(limit)
    result = await db.execute(query)
    subjects = result.scalars().all()
    return [{"id": s.id, "name": s.name, "grade_level": s.grade_level} for s in subjects]


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取学科详情"""
    query = select(
        Subject,
        func.count(KnowledgePoint.id).label("kp_count")
    ).outerjoin(
        KnowledgePoint,
        Subject.id == KnowledgePoint.subject_id
    ).where(Subject.id == subject_id).group_by(Subject.id)

    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="学科不存在")

    subject, kp_count = row
    return SubjectResponse(
        id=subject.id,
        name=subject.name,
        grade_level=subject.grade_level,
        description=subject.description,
        knowledge_points_count=kp_count
    )


@router.get("/{subject_id}/knowledge-points")
async def get_subject_knowledge_points(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取学科的知识点"""
    query = select(KnowledgePoint).where(KnowledgePoint.subject_id == subject_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{subject_id}/suggestions")
async def get_subject_suggestions(
    subject_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """AI 根据学科和用户学习数据生成学习建议"""
    try:
        from app.services.learning_advisor import generate_subject_suggestions
        suggestions = await generate_subject_suggestions(subject_id, user_id, db)
        return suggestions
    except Exception as e:
        return {"suggestions": [], "error": str(e)}
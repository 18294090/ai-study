from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models.question import Question
from app.models.subject import Subject
from app.core.auth import get_current_user

router = APIRouter()

@router.get("/subject-stats")
async def get_subject_statistics(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取学科统计数据"""
    query = select(
        Subject.name,
        func.count(Question.id).label('question_count'),
        func.avg(Question.difficulty).label('avg_difficulty')
    ).outerjoin(Question).group_by(Subject.id)
    
    result = await db.execute(query)
    return [dict(row) for row in result]

@router.get("/difficulty-distribution")
async def get_difficulty_distribution(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取题目难度分布"""
    query = select(
        Question.difficulty,
        func.count(Question.id).label('count')
    ).filter(Question.subject_id == subject_id).group_by(Question.difficulty)
    
    result = await db.execute(query)
    return dict(result)

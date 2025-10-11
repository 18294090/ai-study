from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from app.db.session import get_db
from app.models.question import Question
from app.models.user import User # <-- 导入 User
from app.core.auth import get_current_user
from pydantic import BaseModel # <-- 导入 BaseModel
from typing import List, Optional # <-- 导入 List, Optional

# 为响应定义一个 Pydantic 模型
class KnowledgePointMastery(BaseModel):
    id: int
    name: str
    total_questions: int
    correct_count: int

class SubjectProgressResponse(BaseModel):
    knowledge_points_mastery: List[KnowledgePointMastery]
    total_questions_answered: int
    recent_performance: Optional[float] = None


router = APIRouter()

async def get_total_answered(subject_id: int, user_id: int, db: AsyncSession) -> int:
    # 这是一个辅助函数，需要您实现
    # 示例： return await db.scalar(select(func.count(...)))
    return 0

async def get_recent_performance(subject_id: int, user_id: int, db: AsyncSession) -> Optional[float]:
    # 这是一个辅助函数，需要您实现
    # 示例： return await db.scalar(select(func.avg(...)))
    return 0.0


@router.get("/subject/{subject_id}", response_model=SubjectProgressResponse) # <-- 修改这里
async def get_subject_progress(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取学科学习进度"""
    # 获取知识点掌握度
    mastery_query = select(
        KnowledgePoint.id,
        KnowledgePoint.name,
        func.count(Question.id).label('total_questions'),
        func.sum(case((Question.is_correct == True, 1), else_=0)).label('correct_count')
    ).join(Question).filter(
        Question.subject_id == subject_id,
        Question.answered_by_users.any(id=current_user.id)
    ).group_by(KnowledgePoint.id)
    
    result = await db.execute(mastery_query)
    
    return {
        "knowledge_points_mastery": [dict(row) for row in result],
        "total_questions_answered": await get_total_answered(subject_id, current_user.id, db),
        "recent_performance": await get_recent_performance(subject_id, current_user.id, db)
    }

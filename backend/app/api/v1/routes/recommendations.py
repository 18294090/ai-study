from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models.question import Question
from app.core.auth import get_current_user
from typing import List
import numpy as np

router = APIRouter()

@router.get("/questions/{subject_id}")
async def get_recommended_questions(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """基于用户历史和知识点关联推荐题目"""
    # 获取用户最近做过的题目的知识点
    recent_knowledge_points = await get_user_recent_knowledge_points(current_user.id, db)
    
    # 基于知识点推荐相关题目
    recommended_questions = await db.execute(
        select(Question)
        .filter(
            Question.subject_id == subject_id,
            Question.knowledge_point_id.in_(recent_knowledge_points),
            Question.creator_id != current_user.id
        )
        .order_by(func.random())
        .limit(10)
    )
    
    return recommended_questions.scalars().all()

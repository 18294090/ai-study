from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.db.session import get_db
from app.models.question import Question
from app.models.paper import Paper
from app.core.auth import get_current_user
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/activity")
async def get_user_activity(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取用户活动统计"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # 统计创建的题目数
    questions_created = await db.scalar(
        select(func.count(Question.id))
        .filter(
            Question.creator_id == current_user.id,
            Question.created_at >= start_date
        )
    )
    
    # 统计生成的试卷数
    papers_generated = await db.scalar(
        select(func.count(Paper.id))
        .filter(
            Paper.creator_id == current_user.id,
            Paper.created_at >= start_date
        )
    )
    
    return {
        "questions_created": questions_created,
        "papers_generated": papers_generated,
        "period_days": days
    }

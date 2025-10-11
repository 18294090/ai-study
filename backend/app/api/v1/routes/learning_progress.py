from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.question import Question
from app.models.knowledge_point import KnowledgePoint
from app.core.auth import get_current_user
from datetime import datetime, timedelta

router = APIRouter(prefix="/progress", tags=["learning-progress"])

@router.get("/overview", operation_id="学习进度概览")
async def get_learning_progress(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取学习进度概览"""
    # 获取知识点掌握情况
    mastery_levels = await get_knowledge_point_mastery(subject_id, current_user.id, db)
    
    # 获取最近练习数据
    recent_practice = await get_recent_practice_stats(
        subject_id, 
        current_user.id, 
        days=30, 
        db=db
    )
    
    # 获取薄弱知识点
    weak_points = await identify_weak_points(subject_id, current_user.id, db)
    
    return {
        "mastery_levels": mastery_levels,
        "recent_practice": recent_practice,
        "weak_points": weak_points,
        "suggested_topics": await suggest_next_topics(subject_id, current_user.id, db)
    }

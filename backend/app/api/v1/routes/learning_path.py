from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.knowledge_point import KnowledgePoint
from typing import List, Dict

router = APIRouter(prefix="/learning-path", tags=["learning-path"])

@router.get("/{subject_id}/recommended", operation_id="推荐学习路径")
async def get_recommended_path(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取推荐学习路径"""
    # 获取用户当前掌握程度
    mastery_levels = await get_user_mastery_levels(current_user.id, subject_id, db)
    
    # 基于掌握程度生成推荐路径
    path = await generate_learning_path(subject_id, mastery_levels, db)
    
    return {
        "current_level": calculate_overall_mastery(mastery_levels),
        "recommended_path": path,
        "estimated_completion_time": estimate_completion_time(path)
    }

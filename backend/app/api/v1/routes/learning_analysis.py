from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.auth import get_current_user
from app.services.personalized_learning import PersonalizedLearningPath
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/{subject_id}/effectiveness", operation_id="学习效果分析")
async def analyze_learning_effectiveness(
    subject_id: int,
    period_days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """分析学习效果"""
    # 获取学习数据
    start_date = datetime.utcnow() - timedelta(days=period_days)
    
    # 分析进度
    progress_data = await analyze_progress(
        current_user.id,
        subject_id,
        start_date,
        db
    )
    
    # 生成学习建议
    learning_path = PersonalizedLearningPath()
    recommendations = await learning_path.generate_path(
        current_user.id,
        subject_id,
        db
    )
    
    return {
        "progress_analysis": progress_data,
        "learning_recommendations": recommendations,
        "weak_points": await identify_weak_points(
            current_user.id,
            subject_id,
            db
        )
    }

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.auth import get_current_user
from app.services.learning_predictor import LearningPredictor
from app.services.paper_generator import PaperGenerator

router = APIRouter()

@router.get("/learning-prediction/{subject_id}")
async def predict_learning_progress(
    subject_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """预测学习进度"""
    predictor = LearningPredictor()
    
    # 获取历史学习数据
    study_history = await get_user_study_history(
        current_user.id,
        subject_id,
        db
    )
    
    # 生成预测
    prediction = await predictor.predict_progress(
        current_user.id,
        subject_id,
        study_history,
        days
    )
    
    # 基于预测生成建议
    recommendations = await generate_study_recommendations(
        prediction,
        current_user.id,
        subject_id,
        db
    )
    
    return {
        "prediction": prediction,
        "recommendations": recommendations
    }

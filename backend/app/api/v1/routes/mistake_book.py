from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.question import Question
from app.models.user import User # <-- 导入 User
from app.core.auth import get_current_user
from typing import List
from app.schemas.question import QuestionResponse # <-- 导入 QuestionResponse

router = APIRouter()

@router.get("/", response_model=List[QuestionResponse]) # <-- 修改这里
async def get_mistake_book(
    subject_id: int = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户错题本"""
    query = select(Question).filter(Question.wrong_by_users.any(id=current_user.id))
    if subject_id:
        query = query.filter(Question.subject_id == subject_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/{question_id}")
async def add_to_mistake_book(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """添加题目到错题本"""
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
        
    if current_user not in question.wrong_by_users:
        question.wrong_by_users.append(current_user)
        await db.commit()
    return {"message": "Added to mistake book"}

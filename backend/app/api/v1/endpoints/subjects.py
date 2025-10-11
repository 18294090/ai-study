from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_user  # 确保认证依赖存在
from app.db.session import get_db
from app.models.subject import Subject  # 假设 Subject 模型存在

router = APIRouter()

@router.get("/{subject_id}")
async def get_subject(
    subject_id: int, 
    db: AsyncSession = Depends(get_db), 
    current_user: str = Depends(get_current_user)  # 如果需要认证，保留此行；否则移除
):
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@router.post("/")
async def create_subject(
    subject_data: dict, 
    db: AsyncSession = Depends(get_db), 
    current_user: str = Depends(get_current_user)  # 如果需要认证，保留此行；否则移除
):
    new_subject = Subject(**subject_data)
    db.add(new_subject)
    await db.commit()
    await db.refresh(new_subject)
    return new_subject

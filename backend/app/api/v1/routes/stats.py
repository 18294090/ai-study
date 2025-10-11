from fastapi import APIRouter, Depends
from sqlalchemy import func, and_
from sqlalchemy.future import select
from app.db.session import get_db
from app.core.auth.permissions import teacher_required
from app.core.auth import get_current_user
from app.models.question import Question
from app.models.subject import Subject
from app.models.tag import Tag
from app.models.question import question_tags
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.VectorStore import DocumentChunk
from app.models.book import Book

router = APIRouter()

@router.get("/overview")
async def get_stats(
    current_user = Depends(teacher_required),
    db: AsyncSession = Depends(get_db)
):
    """获取统计概览"""
    stats = {
        "total_questions": await db.scalar(select(func.count(Question.id))),
        "subjects_count": await db.scalar(select(func.count(Subject.id))),
        "my_questions": await db.scalar(
            select(func.count(Question.id))
            .filter(Question.creator_id == current_user.id)
        )
    }
    return stats

@router.get("/difficulty-analysis")
async def analyze_difficulty(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """分析题目难度分布"""
    query = select(
        Question.difficulty,
        func.count(Question.id).label('count')
    ).filter(
        Question.subject_id == subject_id
    ).group_by(Question.difficulty)    
    result = await db.execute(query)
    stats = {}
    for difficulty, count in result:
        stats[f"难度{difficulty}"] = count    
    return stats

@router.get("/tag-analysis")
async def analyze_tags(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """分析标签使用情况"""
    query = select(
        Tag.name,
        func.count(question_tags.c.question_id).label('count')
    ).join(question_tags).join(Question).filter(
        Question.subject_id == subject_id
    ).group_by(Tag.name)
    
    result = await db.execute(query)
    return dict(result.fetchall())


@router.get("/subject/", summary="获取统计信息")
async def get_stats(db: AsyncSession = Depends(get_db),subject_id: int = None):
    """
    获取文档数量和问题数量。
    """
    try:
        documents_chunk_count = await db.scalar(select(func.count(DocumentChunk.id)).filter(DocumentChunk.subject_id == subject_id))
        books_count = await db.scalar(select(func.count(Book.id)).filter(Book.subject_id == subject_id))
        questions_count = await db.scalar(select(func.count(Question.id)).filter(Question.subject_id == subject_id))        
        return {"documents_count": books_count, "questions_count": questions_count, "documents_chunk_count": documents_chunk_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")
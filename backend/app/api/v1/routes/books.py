# app/api/v1/routes/books.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.book import Book
from app.models.VectorStore import DocumentChunk  # 添加导入
from app.schemas.book import BookCreate, BookResponse, ProcessDocumentRequest
router = APIRouter()


@router.post("/create", response_model=BookResponse, summary="创建书籍记录")
async def create_book(
    book_data: BookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建书籍记录（不处理文件）。
    """
    book = Book(**book_data.dict(), user_id=current_user.id)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book

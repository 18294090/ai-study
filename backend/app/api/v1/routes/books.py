# app/api/v1/routes/books.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.embedding import vectorize_and_store_document
from app.core.auth import get_current_user
from app.models.user import User
from app.models.book import Book
from app.models.VectorStore import DocumentChunk  # 添加导入
from app.schemas.book import BookCreate, BookResponse, ProcessDocumentRequest
router = APIRouter()
@router.post("/process", summary="处理文档：切片、向量化、存储")
async def process_document(
    request: ProcessDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    传入文件路径，切片，向量化，存储到 pgvector。
    文件应已通过 /file/upload 上传。
    """
    try:
        await vectorize_and_store_document(
            file_path=request.file_path,
            title=request.title,
            book_id=request.book_id,
            user_id=current_user.id,
            db=db
        )
        return {"message": "文档处理并存储成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

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

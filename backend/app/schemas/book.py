import datetime
from typing import Optional
from pydantic import BaseModel

class BookBase(BaseModel):
    """
    书籍基础模型
    """
    title: str
    content: Optional[str] = None
    subject_id: Optional[int] = None

class BookCreate(BaseModel):
    """
    书籍创建模型
    """
    title: str
    content: Optional[str] = None
    subject_id: Optional[int] = None

class BookResponse(BaseModel):
    """
    书籍响应模型
    """
    id: int
    title: str
    content: Optional[str] = None
    user_id: int
    subject_id: Optional[int] = None

class BookUpdate(BaseModel):
    """
    书籍更新模型
    """
    title: Optional[str] = None
    content: Optional[str] = None
    subject_id: Optional[int] = None


class ProcessDocumentRequest(BaseModel):
    file_path: str
    title: str
    book_id: int
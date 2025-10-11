# 问题CRUD
from sqlalchemy.ext.asyncio import AsyncSession
from .base import CRUDBase
from app.models.question import Question
from app.schemas.question import QuestionCreate, QuestionUpdate


from typing import List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.sql import or_

class QuestionCRUD(CRUDBase[Question, QuestionCreate, QuestionUpdate]):
    async def create_with_author(
        self, db: AsyncSession, *, obj_in: QuestionCreate, author_id: int
    ) -> Question:
        """
        创建一个关联了作者的新问题。
        """
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data, author_id=author_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        keyword: Optional[str] = None,
        type: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> List[Question]:
        """
        获取问题列表，支持搜索
        """
        query = select(self.model).order_by(self.model.created_at.desc())
        
        # 添加搜索条件
        if keyword and keyword.strip():
            query = query.where(
                or_(
                    self.model.title.ilike(f"%{keyword.strip()}%"),
                    self.model.content.ilike(f"%{keyword.strip()}%")
                )
            )
        if type and type.strip():
            query = query.where(self.model.type == type.strip())
        if subject:
            query = query.where(self.model.subject.ilike(f"%{subject}%"))
            
        # 添加分页
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def count(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        type: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> int:
        """
        计算符合条件的问题总数
        """
        query = select(func.count()).select_from(self.model)
        
        # 添加搜索条件
        if keyword:
            query = query.where(
                or_(
                    self.model.title.ilike(f"%{keyword}%"),
                    self.model.content.ilike(f"%{keyword}%")
                )
            )
        if type:
            query = query.where(self.model.type == type)
        if subject:
            query = query.where(self.model.subject.ilike(f"%{subject}%"))
            
        result = await db.execute(query)
        return result.scalar() or 0
    
    async def get_all_tags(self, db: AsyncSession) -> List[str]:
        """获取所有已使用的标签"""
        query = text("""
            SELECT DISTINCT jsonb_array_elements_text(tags::jsonb)
            FROM questions
            ORDER BY jsonb_array_elements_text
        """)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_all_knowledge_points(self, db: AsyncSession) -> List[str]:
        """获取所有已使用的知识点"""
        query = text("""
            SELECT DISTINCT jsonb_array_elements_text(knowledge_points::jsonb)
            FROM questions
            ORDER BY jsonb_array_elements_text
        """)
        result = await db.execute(query)
        return result.scalars().all()
    

question = QuestionCRUD(Question)

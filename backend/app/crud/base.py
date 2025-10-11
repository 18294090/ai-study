# app/crud/base.py
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
FilterType = TypeVar("FilterType", bound=BaseModel)
class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A SQLAlchemy model class
        """
        self.model = model

    async def get(
        self, db: AsyncSession, id: Any, *, load_relationships: Optional[List[str]] = None
    ) -> Optional[ModelType]:#获取单个对象
        query = select(self.model)
        if load_relationships:
            for relationship in load_relationships:
                query = query.options(selectinload(getattr(self.model, relationship)))
        query = query.filter(self.model.id == id)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        load_relationships: Optional[List[str]] = None,
    ) -> List[ModelType]:#获取多个对象
        query = select(self.model)
        if load_relationships:
            for relationship in load_relationships:
                query = query.options(selectinload(getattr(self.model, relationship)))
        query = query.order_by(self.model.id).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_multi_paginated(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        load_relationships: Optional[List[str]] = None,
    ) -> tuple[List[ModelType], int]:
        """获取带分页信息（总数）的多个对象"""
        count_query = select(func.count(self.model.id))
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = select(self.model)
        if load_relationships:
            for relationship in load_relationships:
                query = query.options(selectinload(getattr(self.model, relationship)))
        query = query.order_by(self.model.id.desc()).offset(skip).limit(limit)
        items_result = await db.execute(query)
        items = list(items_result.scalars().all())
        return items, total

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, db_obj: ModelType) -> ModelType:
        """
        从数据库中删除一个对象。
        """
        await db.delete(db_obj)
        await db.commit()
        return db_obj
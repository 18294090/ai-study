# 基础模型
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional, Set
from sqlalchemy import Column, DateTime, Integer, MetaData, Table
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedColumn,
    mapped_column,
)

class Base(DeclarativeBase):
    """提供公共字段和自动表名的声明基类。"""

    __abstract__ = True
    __tablename__: ClassVar[str]

    # 声明所有表都应该有的列
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "__tablename__" not in cls.__dict__:
            cls.__tablename__ = cls._camel_to_snake(cls.__name__)

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        chars = []
        for idx, char in enumerate(name):
            if char.isupper() and idx != 0:
                chars.append("_")
            chars.append(char.lower())
        return "".join(chars)

    def dict(self, exclude: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        将模型实例转换为字典
        
        参数:
            exclude: 要排除的字段集合
            
        返回:
            Dict[str, Any]: 模型数据的字典表示
        """
        if exclude is None:
            exclude = set()
        # 获取表对象，确保它存在
        table = self.__class__.__table__
        
        return {
            c.name: getattr(self, c.name)
            for c in table.columns
            if c.name not in exclude
        }

    def update(self, **kwargs: Any) -> None:
        """
        更新模型实例的属性
        
        参数:
            kwargs: 要更新的属性和值
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
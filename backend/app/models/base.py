# 基础模型
from datetime import datetime
from typing import Any, Dict, Optional, Set
from sqlalchemy import Column, DateTime, Integer, MetaData, Table
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedColumn,
    declared_attr,
    mapped_column,
)

class Base(DeclarativeBase):
    """
    SQLAlchemy 声明性基类
    
    包含所有模型共享的通用属性和方法
    """
    # 声明所有表都应该有的列
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 生成 __tablename__ 属性
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """
        自动生成表名
        将类名转换为小写下划线形式
        例如: UserProfile -> user_profile
        """
        name = cls.__name__
        # 将驼峰命名转换为下划线命名
        return ''.join(
            ['_' + c.lower() if c.isupper() else c for c in name]
        ).lstrip('_')

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
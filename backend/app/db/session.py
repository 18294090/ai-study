# 会话工厂

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from app.core.config import Settings

# 从配置中获取数据库 URL
settings = Settings()

# 创建异步数据库引擎
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DB_ECHO,
    poolclass=NullPool,
    pool_pre_ping=True,
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# FastAPI 依赖函数
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()



from app.db.session import AsyncSessionLocal
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """获取异步数据库会话

    用作 FastAPI 依赖项
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
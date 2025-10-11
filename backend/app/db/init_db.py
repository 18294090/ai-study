# 初始化数据库
import logging
from app.db.session import engine
from app.db.base import Base
from sqlalchemy import text

# 在这里导入所有模型，以便 Base.metadata 能发现它们
from app.models.user import User
from app.models.subject import Subject
from app.models.question import Question, QuestionComment  # <-- 修改这里
from app.models.log import OperationLog  
from app.models.book import Book  
# ... 导入其他所有模型 ...
logger = logging.getLogger(__name__)

async def init_db() -> None:
    """
    在数据库中创建所有表。
    """
    logger.info("Creating database tables...")
    # 创建 pgvector 扩展
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    # 创建所有表
    async with engine.begin() as conn:
        # 在这里，Base.metadata 已经包含了所有已导入模型的元数据
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")

async def close_db() -> None:
    """
    关闭数据库连接池。
    """
    logger.info("Closing database connection pool...")
    await engine.dispose()
    logger.info("Database connection pool closed.")

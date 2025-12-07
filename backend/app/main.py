#app/main.py
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings, setup_app_logging
from app.core.security import setup_security_middleware # <-- 确认这个导入是正确的
from app.db.init_db import init_db, close_db
from app.utils.exception_handlers import setup_exception_handlers # 导入异常处理器
# 临时路由，直到我们创建实际的 API 路由
from app.api.v1 import api_v1_router
from fastapi_mcp import FastApiMCP
# 导入所有模型确保它们被注册
import app.models
from app.db.neo4j_utils import driver, close_driver
# 配置日志 (在加载配置后立即设置)
setup_app_logging(config=settings)
logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("Starting application...")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Database: {settings.DATABASE_URL}")    
    try:
        # 创建数据库表（生产环境应使用迁移工具）
        if settings.CREATE_DB_TABLES:
            await init_db()  # <-- 修改这里
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise    

    # 检查 Neo4j 连接（如果使用异步驱动）
    try:
        # 如果driver是异步的，使用await
        # await driver.verify_connectivity()
        driver.verify_connectivity()  # 假设同步
        logger.info("Neo4j connected")
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        # 可以选择不raise，让应用继续运行

    yield  # 应用运行    
    close_driver()
    # 关闭时执行
    logger.info("Shutting down application...")
    try:
        await close_db()  # <-- 修改这里
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        raise

def create_application() -> FastAPI:
    """应用工厂函数"""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        docs_url="/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.DOCS_ENABLED else None,
        openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
        lifespan=lifespan,
        swagger_ui_parameters={
            "custom_css_url": "https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.3/swagger-ui.css",
            "custom_js_url": "https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.3/swagger-ui-bundle.js"
        }
    )
    # 设置中间件
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],  # 允许的前端源
        allow_credentials=True,  # 允许携带凭据
        allow_methods=["*"],     # 允许所有HTTP方法
        allow_headers=["*"],     # 允许所有头部
        expose_headers=["*"]     # 公开所有响应头
    )
    # 挂载静态文件目录
    uploads_dir = Path(settings.UPLOAD_DIR)
    if not uploads_dir.exists():
        uploads_dir.mkdir(parents=True, exist_ok=True)  # 添加exist_ok=True
    application.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
    # 添加安全中间件（自定义）
    setup_security_middleware(application)    
    # 添加自定义中间件示例
    @application.middleware("http")
    async def log_requests(request: Request, call_next):
        """日志记录中间件"""
        logger.info(f"Request: {request.method} {request.url}")
        response = await call_next(request)
        return response
    # 注册路由
    application.include_router(api_v1_router, prefix="/api/v1")  # <-- 修改前缀为 /api
    # 设置异常处理器
    setup_exception_handlers(application)  
    # 添加根路由
    @application.get("/", include_in_schema=False)
    async def root():        
        return {
            "message": f"Welcome to {settings.PROJECT_NAME}",
            "version": settings.VERSION,
            "docs": "/docs",
            "status": "/internal/health"
        }
    
    # 添加公开的健康检查路由
    @application.get("/health", include_in_schema=False)
    async def health_check():
        """健康检查接口"""
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    # 创建并挂载 MCP 服务器
    mcp_server = FastApiMCP(application)
    mcp_server.mount(mount_path="/mcp")
    return application
# 创建FastAPI应用实例
app = create_application()
# 热重载时可能需要（如果直接运行此文件）
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
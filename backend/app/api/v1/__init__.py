from fastapi import APIRouter
from .routes.auth import router as auth_router
from .routes.subjects import router as subjects_router
from .routes.questions import router as questions_router
from .routes.knowledge_points import router as knowledge_points_router
from .routes.analysis import router as analysis_router
from .routes.mistake_book import router as mistake_book_router
from .routes.user_progress import router as user_progress_router
from .routes.files import router as files_router
from .routes.books import router as books_router
from .routes.applications import router as applications_router
from .routes.classes import router as classes_router
from .routes.resources import router as resources_router
from .routes.knowledge_extraction import router as knowledge_extraction_router

api_v1_router = APIRouter()

# 核心路由注册
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(subjects_router, prefix="/subjects", tags=["subjects"])
api_v1_router.include_router(classes_router, prefix="/classes", tags=["classes"])
api_v1_router.include_router(questions_router, prefix="/questions", tags=["questions"])
api_v1_router.include_router(knowledge_points_router, tags=["knowledge-points"])
api_v1_router.include_router(resources_router, prefix="/resources", tags=["resources"])
api_v1_router.include_router(knowledge_extraction_router, prefix="/knowledge-extraction", tags=["knowledge-extraction"])
api_v1_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_v1_router.include_router(mistake_book_router, prefix="/mistake-book", tags=["mistake-book"])
api_v1_router.include_router(user_progress_router, prefix="/user-progress", tags=["user-progress"])
api_v1_router.include_router(files_router, tags=["files"])
api_v1_router.include_router(books_router, prefix="/books", tags=["books"])
api_v1_router.include_router(applications_router, prefix="/applications", tags=["applications"])


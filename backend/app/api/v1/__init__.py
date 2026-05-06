from fastapi import APIRouter
from .routes.auth import router as auth_router
from .routes.subjects import router as subjects_router
from .routes.questions import router as questions_router
from .routes.knowledge_points import router as knowledge_points_router
from .routes.knowledge_extraction import router as knowledge_extraction_router
from .routes.mastery import router as mastery_router
from .routes.tutor import router as tutor_router
from .routes.irt import router as irt_router
from .routes.fsrs import router as fsrs_router
from .routes.expert_reviewer import router as expert_reviewer_router
from .routes.audit import router as audit_router
from .routes.study_groups import router as study_groups_router

api_v1_router = APIRouter()

# 核心路由注册
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(subjects_router, prefix="/subjects", tags=["subjects"])
api_v1_router.include_router(questions_router, prefix="/questions", tags=["questions"])
api_v1_router.include_router(knowledge_points_router, tags=["knowledge-points"])
api_v1_router.include_router(knowledge_extraction_router, prefix="/knowledge-extraction", tags=["knowledge-extraction"])
api_v1_router.include_router(mastery_router, prefix="/mastery", tags=["mastery"])
api_v1_router.include_router(tutor_router, prefix="/tutor", tags=["tutor"])
api_v1_router.include_router(irt_router, prefix="/irt", tags=["irt"])
api_v1_router.include_router(fsrs_router, prefix="/fsrs", tags=["fsrs"])
api_v1_router.include_router(expert_reviewer_router, prefix="/expert-reviewer", tags=["expert-reviewer"])
api_v1_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_v1_router.include_router(study_groups_router, prefix="/study-groups", tags=["study-groups"])
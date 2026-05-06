from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import os
import shutil
import tempfile
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.subject import Subject
from app.schemas.subject import SubjectCreate
from app.core.config import settings

router = APIRouter()

SUBJECT_TRESHOLD = 0.6


async def get_or_create_subject(
    db: AsyncSession,
    name: str,
    grade_level: Optional[str],
    user_id: int
) -> Subject:
    """Get existing subject by name or create new one."""
    query = select(Subject).where(Subject.name == name)
    result = await db.execute(query)
    subject = result.scalar_one_or_none()

    if subject:
        return subject

    subject_data = SubjectCreate(name=name, grade_level=grade_level)
    subject = Subject(
        **subject_data.dict(),
        user_id=user_id,
        creator_id=user_id,
    )
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return subject


async def process_knowledge_extraction(
    file_path: str,
    subject_id: int,
    user_id: int
):
    try:
        from app.kg.src.parsers.multi_parser import parse_document
        from app.kg.agents.lead_agent import run_pipeline
        from app.kg.src.config import get_config

        textbook = parse_document(file_path)
        textbook.textbook_id = f"textbook_{subject_id}_{user_id}"
        textbook.subject = str(subject_id)

        cfg = get_config()
        result = await run_pipeline(
            textbook_id=textbook.textbook_id,
            chapters=textbook.chapters,
            eval_threshold=cfg.eval.default_threshold,
        )

        if not result.get("eval_passed", False):
            print(f"[pipeline] eval gate failed for {textbook.textbook_id}")
            return

        print(f"[pipeline] Success for {textbook.textbook_id}")

    except Exception as e:
        print(f"[pipeline] Extraction task failed: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("/extract", operation_id="从文件提取知识点")
async def extract_knowledge_from_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传教材/文档，AI自动识别学科和学段，提取知识点并构建图谱
    """
    if not file.filename.endswith(('.pdf', '.docx', '.txt', '.md')):
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)

    try:
        await file.seek(0)
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    try:
        from app.kg.src.parsers.multi_parser import parse_document
        from app.services.subject_detector import detect_subject_and_grade, extract_textbook_info

        textbook = parse_document(file_path)

        title, first_content = extract_textbook_info(
            "\n".join([ch.content for ch in textbook.chapters])
        )
        subject_name, grade_level = await detect_subject_and_grade(title, first_content)

        if subject_name == "未知":
            raise HTTPException(
                status_code=422,
                detail="无法识别教材学科，请手动指定学科"
            )

        subject = await get_or_create_subject(
            db, subject_name, grade_level, current_user.id
        )

        textbook.textbook_id = f"textbook_{subject.id}_{current_user.id}"
        textbook.subject = str(subject.id)

        from app.kg.agents.lead_agent import run_pipeline
        from app.kg.src.config import get_config

        cfg = get_config()
        result = await run_pipeline(
            textbook_id=textbook.textbook_id,
            chapters=textbook.chapters,
            eval_threshold=cfg.eval.default_threshold,
        )

        if not result.get("eval_passed", False):
            return {
                "message": "文件已上传，知识点提取进行中（评估未通过）",
                "filename": file.filename,
                "subject_detected": subject_name,
                "grade_level": grade_level,
            }

        return {
            "message": "知识点提取成功",
            "filename": file.filename,
            "subject_id": subject.id,
            "subject_name": subject_name,
            "grade_level": grade_level,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.post("/exam/compare")
async def compare_exam_extraction(
    file: UploadFile = File(...),
    use_hermes: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare Hermes vs LangGraph exam extraction."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)

    try:
        await file.seek(0)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        results = {}

        if use_hermes:
            from app.hermes.skills.exam_skill import run_exam_skill
            hermes_result = await run_exam_skill({"file_path": file_path})
            results["hermes"] = hermes_result

        if not use_hermes:
            from app.services.exam_parser.agent.exam_agent import ExamAgent
            agent = ExamAgent(file_path)
            langgraph_result = agent.run()
            results["langgraph"] = langgraph_result

        return {
            "hermes": results.get("hermes", {}),
            "langgraph": results.get("langgraph", {}),
            "comparison_available": True,
        }

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rmdir(temp_dir)
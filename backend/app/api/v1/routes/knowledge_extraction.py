from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import os
import shutil
import tempfile
from app.db.session import get_db, AsyncSessionLocal
from app.core.auth import get_current_user
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint, KnowledgePointRelationship
from app.services.document_splitter import split_exam_paper # 复用文档加载逻辑
from app.services.knowledge_extraction import KnowledgeExtractionService
from app.services.knowledge_graph_builder import KnowledgeGraphBuilder
from app.core.config import settings
from app.db.neo4j_utils import create_typed_relation

router = APIRouter()

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


@router.post("/extract/{subject_id}", operation_id="从文件提取知识点")
async def extract_knowledge_from_file(
    subject_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传教材/文档，自动提取知识点并构建图谱
    """
    if not file.filename.endswith(('.pdf', '.docx', '.txt', '.md')):
        raise HTTPException(status_code=400, detail="不支持的文件格式")
        
    # 保存临时文件
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    
    try:
        # 确保文件指针在开始位置
        await file.seek(0)
        # 使用异步读取并写入文件
        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
        
    # 添加后台任务
    background_tasks.add_task(
        process_knowledge_extraction,
        file_path,
        subject_id,
        current_user.id
    )
    
    return {"message": "文件已上传，正在后台提取知识点", "filename": file.filename}

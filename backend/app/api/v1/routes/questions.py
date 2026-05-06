from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
import aiofiles
import uuid
import pandas as pd
import io
import os
import tempfile
from pathlib import Path
from app.db.session import get_db
from app.models.question import Question, QuestionComment
from app.schemas.question import QuestionCreate, QuestionResponse, CommentCreate, QuestionUpdate
from app.core.auth import get_current_user, get_current_active_user  
from app.models.user import User
from app.models.knowledge import KnowledgePoint
# 导入exam_parser (Agent-based extraction)
from app.services.exam_parser import run_exam_agent_sync
# 导入向量化服务
from app.services.question_vectorization import vectorize_questions_batch, search_similar_questions
from app.models.VectorStore import QuestionVectorResponse

router = APIRouter()

@router.get("/public", response_model=List[QuestionResponse])
async def get_public_questions(
    subject_id: Optional[int] = None,
    difficulty: Optional[int] = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """获取公开题目列表（不需要认证）"""
    query = select(Question).filter(Question.status == "active")  # 只返回已发布的题目
    
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if subject_id:
        query = query.filter(Question.subject_id == subject_id)
    
    result = await db.execute(query.offset(skip).limit(limit))
    questions = result.scalars().all()
    return questions

@router.get("/", response_model=List[QuestionResponse])
async def get_questions(
    subject_id: Optional[int] = None,
    keyword: Optional[str] = None,
    type: Optional[str] = None,
    knowledge_point_id: Optional[int] = None,
    difficulty: Optional[int] = None,
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取题目列表，支持筛选和分页"""
    query = select(Question)
    if knowledge_point_id:
        query = query.filter(Question.knowledge_points.any(KnowledgePoint.id == knowledge_point_id))
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if subject_id:
        query = query.filter(Question.subject_id == subject_id)
    if type:
        query = query.filter(Question.type == type)
    if keyword:
        query = query.filter(
            or_(
                Question.title.ilike(f"%{keyword}%"),
                Question.content.ilike(f"%{keyword}%")
            )
        )
    result = await db.execute(query.offset(skip).limit(limit))
    questions = result.scalars().all()
    return questions

@router.get("/search", response_model=List[QuestionResponse])
async def search_questions(
    keyword: Optional[str] = None,
    subject_id: Optional[int] = None,
    knowledge_point_id: Optional[int] = None,
    difficulty: Optional[int] = None,
    page: int = Query(1, gt=0),
    per_page: int = Query(10, gt=0, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取题目列表，支持筛选和分页"""
    query = select(Question)
    filters = []    
    if keyword:
        filters.append(
            or_(
                Question.title.ilike(f"%{keyword}%"),
                Question.content.ilike(f"%{keyword}%")
            )
        )
    if subject_id:
        filters.append(Question.subject_id == subject_id)
    if knowledge_point_id:
        filters.append(Question.knowledge_points.any(KnowledgePoint.id == knowledge_point_id))
    if difficulty:
        filters.append(Question.difficulty == difficulty)
    if filters:
        query = query.filter(and_(*filters))    
    # 分页
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    return result.scalars().all()

async def process_file_import(file_path: str, file_type: str, user_id: int, subject_id: Optional[int], db: AsyncSession):
    """处理文件导入的后台任务 - 使用 Agent-based extraction"""
    try:
        print(f"Processing {file_type} import for user {user_id}...")

        # 根据文件类型调用相应的解析器 (统一使用 MinerU + Agent)
        if file_type == 'pdf':
            result = run_exam_agent_sync(file_path, source=file_path)
            questions_data = result.get("questions", [])
            print(f"Agent extracted {len(questions_data)} questions, report: {result.get('report', {})}")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for exam parsing: {file_type}. Only PDF is supported.")

        # Convert agent output to Question objects
        from app.services.exam_parser import Question
        questions = []
        for q_data in questions_data:
            content = q_data.get("内容", "")
            questions.append(Question(
                内容=content,
                来源=q_data.get("页码", "unknown"),
                题型=q_data.get("题型", "未知"),
                配图=q_data.get("配图", []),
                材料=q_data.get("材料", ""),
                题号=q_data.get("id"),
            ))
        
        # 将解析的题目进行向量化并存储到向量数据库
        question_vectors = await vectorize_questions_batch(
            parsed_questions=questions,
            user_id=user_id,
            subject_id=subject_id,
            db=db
        )
        
        await db.commit()
        
        print(f"Successfully vectorized and imported {len(question_vectors)} questions from {file_type} file.")        
    except Exception as e:
        print(f"Error processing file import: {str(e)}")
        await db.rollback()
        raise
    finally:
        # 清理上传的临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass  # 忽略删除失败的错误

@router.post("/batch-import")
async def batch_import_questions(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)  # 临时改为普通用户权限
):
    """批量导入题目,接收PDF文件 (Agent-based extraction)"""
    # 检查文件类型 - 只允许 PDF
    allowed_extensions = ['.pdf']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"只允许上传以下格式的文件: {', '.join(allowed_extensions)}"
        )
    
    # 保存上传的文件到临时位置
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    # 确定文件类型
    if file_ext == '.pdf':
        file_type = 'pdf'
    elif file_ext in ['.docx', '.doc']:
        file_type = 'docx' if file_ext == '.docx' else 'doc'
    else:
        file_type = 'image'
    
    # 在后台任务中处理导入
    background_tasks.add_task(
        process_file_import, 
        temp_file_path,
        file_type,
        current_user.id,
        subject_id,
        db
    )
    
    return {"message": f"{file.filename} 导入已开始", "status": "processing"}

@router.post("/{question_id}/comments")
async def add_comment(
    question_id: int,
    comment: CommentCreate,
    db: AsyncSession = Depends(get_db), # <-- 添加 db 依赖
    current_user = Depends(get_current_user)
):
    """添加题目评论"""
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    db_comment = QuestionComment(
        content=comment.content,
        question_id=question_id,
        user_id=current_user.id
    )
    db.add(db_comment)
    await db.commit()
    return db_comment

#编辑修改题目
@router.put("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    question: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """更新题目"""
    db_question = await db.get(Question, question_id)
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    if db_question.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this question")
    for key, value in question.dict(exclude_unset=True).items():
        setattr(db_question, key, value)
    await db.commit()
    await db.refresh(db_question)
    return db_question

#删除题目
@router.delete("/{question_id}")
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """删除题目"""
    db_question = await db.get(Question, question_id)
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    if db_question.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this question")
    await db.delete(db_question)
    await db.commit()
    return {"message": "Question deleted successfully"}
#获取题目详情
@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取题目详情"""
    question = await db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

@router.get("/vector/search", response_model=List[QuestionVectorResponse])
async def search_question_vectors(
    query: str = Query(..., description="搜索查询"),
    subject_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50, description="返回结果数量"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """语义搜索试题向量"""
    try:
        similar_questions = await search_similar_questions(
            query=query,
            user_id=current_user.id,
            subject_id=subject_id,
            limit=limit,
            db=db
        )
        
        # 转换为响应格式
        results = []
        for q in similar_questions:
            results.append(QuestionVectorResponse(
                id=q.id,
                content=q.content,
                embedding=[],  # 不返回向量数据
                title=q.title,
                question_type=q.question_type,
                difficulty=q.difficulty,
                source=q.source,
                subject_id=q.subject_id,
                user_id=q.user_id,
                tags=q.tags,
                created_at=q.created_at
            ))
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

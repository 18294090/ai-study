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
from app.core.permissions import user_required  
from app.models.user import User
from app.models.knowledge import KnowledgePoint
# 导入exam_parser
from app.services.exam_parser import parse_pdf, parse_docx, parse_image
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

@router.post("/", response_model=QuestionResponse)
async def create_question(
    question: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """创建新题目"""
    # 创建题目对象，富文本内容已包含在question中
    db_question = Question(**question.dict(exclude={"knowledge_point_ids"}), author_id=current_user.id)    
    # 处理知识点关联
    if question.knowledge_point_ids:
        # 查询知识点
        knowledge_point_query = select(KnowledgePoint).filter(
            KnowledgePoint.id.in_(question.knowledge_point_ids)
        )
        result = await db.execute(knowledge_point_query)
        knowledge_points = result.scalars().all()
        db_question.knowledge_points = knowledge_points
    db.add(db_question)
    await db.commit()
    await db.refresh(db_question)
    return db_question

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
    """处理文件导入的后台任务"""
    img_dir = None
    try:
        print(f"Processing {file_type} import for user {user_id}...")        
        # 使用backend/uploads目录保存图片
        import os
        from pathlib import Path
        uploads_dir = Path(__file__).parent.parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        
        # 创建以用户ID和时间戳命名的子目录
        import time
        timestamp = int(time.time())
        img_dir = uploads_dir / f"user_{user_id}_{timestamp}"
        img_dir.mkdir(exist_ok=True)        
        # 根据文件类型调用相应的解析器
        if file_type == 'pdf':
            questions = parse_pdf(file_path, str(img_dir))
        elif file_type in ['docx', 'doc']:
            questions = parse_docx(file_path, str(img_dir))
        elif file_type in ['png', 'jpg', 'jpeg']:
            questions = parse_image(file_path, str(img_dir))
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # 处理题目内容中的图片路径
        for question in questions:
            if question.配图:  # 配图是图片路径列表
                # 将绝对路径转换为相对路径（相对于uploads目录）
                relative_images = []
                for img_path in question.配图:
                    if os.path.isabs(img_path):
                        # 转换为相对于uploads目录的路径
                        try:
                            img_path_obj = Path(img_path)
                            relative_path = img_path_obj.relative_to(uploads_dir)
                            relative_images.append(f"/uploads/{relative_path}")
                        except ValueError:
                            # 如果无法转换为相对路径，保持原路径
                            relative_images.append(img_path)
                    else:
                        relative_images.append(f"/uploads/{img_path}")
                question.配图 = relative_images
            
            # 同时更新content中的图片路径
            if question.内容 and '<img src=' in question.内容:
                import re
                def replace_img_src(match):
                    src = match.group(1)
                    if os.path.isabs(src):
                        try:
                            src_obj = Path(src)
                            relative_path = src_obj.relative_to(uploads_dir)
                            return f"<img src='/uploads/{relative_path}'>"
                        except ValueError:
                            return match.group(0)
                    else:
                        return f"<img src='/uploads/{src}'>"
                
                question.内容 = re.sub(r"<img src='([^']+)'", replace_img_src, question.内容)
                question.内容 = re.sub(r'<img src="([^"]+)"', replace_img_src, question.内容)
        
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
        # 清理上传的临时文件，但保留uploads目录中的图片
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass  # 忽略删除失败的错误
            import shutil
            shutil.rmtree(img_dir)

@router.post("/batch-import")
async def batch_import_questions(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user)  # 临时改为普通用户权限
):
    """批量导入题目,接收pdf，word，图片文件"""
    # 检查文件类型
    allowed_extensions = ['.pdf', '.docx', '.doc', '.png', '.jpg', '.jpeg']
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

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from typing import List, Optional
import aiofiles
import uuid
import pandas as pd
import io
from app.db.session import get_db
from app.models.question import Question
from app.schemas.question import QuestionCreate, QuestionResponse, CommentCreate, QuestionUpdate
from app.core.auth import get_current_user, get_current_active_user
from app.core.permissions import teacher_required  
from app.models.user import User

router = APIRouter()

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
        query = query.filter(Question.knowledge_point_id == knowledge_point_id)
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
        filters.append(Question.knowledge_point_id == knowledge_point_id)
    if difficulty:
        filters.append(Question.difficulty == difficulty)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # 分页
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    return result.scalars().all()

def process_questions_import(df: pd.DataFrame, user_id: int, db: AsyncSession):
    # 这是一个后台任务的示例实现，您需要根据实际情况填充逻辑
    print(f"Processing import for user {user_id}...")
    # for index, row in df.iterrows():
    #     ... create question object and add to db session ...
    # db.commit()
    print("Import finished.")

@router.post("/batch-import")
async def batch_import_questions(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(teacher_required)
):
    """批量导入题目"""
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="只允许上传Excel文件")
    
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    
    # 在后台任务中处理导入，确保处理富文本内容
    background_tasks.add_task(
        process_questions_import, 
        df, 
        current_user.id, 
        db
    )
    return {"message": "导入已开始", "status": "processing"}

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

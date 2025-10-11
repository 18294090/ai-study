from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.question import Question
from app.utils.validators import validate_question_data
import pandas as pd
import io

router = APIRouter()

@router.post("/questions/validate", operation_id="题目验证")
async def validate_questions_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """验证题目数据"""
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="只支持Excel文件格式")
    
    content = await file.read()
    df = pd.read_excel(io.BytesIO(content))
    validation_results = await validate_question_data(df, db)
    return validation_results

@router.post("/questions/import", operation_id="题目导入")
async def import_questions(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """批量导入题目"""
    # ...验证逻辑...
    questions = []
    for _, row in df.iterrows():
        question = Question(
            title=row['题目标题'],
            content=row['题目内容'],
            answer=row['答案'],
            difficulty=row['难度'],
            subject_id=row['学科ID'],
            knowledge_point_id=row['知识点ID'],
            creator_id=current_user.id
        )
        questions.append(question)
    
    db.add_all(questions)
    await db.commit()
    return {"message": f"成功导入 {len(questions)} 道题目"}

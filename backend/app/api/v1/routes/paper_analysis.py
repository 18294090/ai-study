from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.paper import Paper
from app.core.auth import get_current_user
from app.utils.paper_analysis import calculate_difficulty_score

router = APIRouter()

@router.get("/{paper_id}/analysis")
async def analyze_paper(
    paper_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """分析试卷难度和知识点覆盖"""
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    # 计算试卷整体难度
    difficulty_score = calculate_difficulty_score(paper.questions)
    
    # 分析知识点覆盖
    knowledge_coverage = await analyze_knowledge_coverage(paper, db)
    
    # 分析题型分布
    question_type_distribution = analyze_question_types(paper.questions)
    
    return {
        "difficulty_score": difficulty_score,
        "knowledge_coverage": knowledge_coverage,
        "question_type_distribution": question_type_distribution,
        "estimated_time": estimate_completion_time(paper.questions)
    }

# 试题向量化服务
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from langchain_ollama import OllamaEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector
from app.models.VectorStore import QuestionVector, QuestionVectorCreate
from app.services.exam_parser.core import Question

# 初始化本地 Ollama 嵌入模型
embeddings = OllamaEmbeddings(model="bge-m3", base_url="http://localhost:11434")

async def vectorize_question(
    parsed_question: Question,
    user_id: int,
        subject_id: Optional[int] = None,
    db: AsyncSession = None
) -> QuestionVector:
    """
    将解析出的试题进行向量化并存储
    Args:
        parsed_question: 解析出的试题对象
        user_id: 用户ID
        subject_id: 学科ID（可选）
        db: 数据库会话
    Returns:
        QuestionVector: 向量化的试题对象
    """
    # 构建试题内容用于向量化
    content_to_embed = f"""
标题: {parsed_question.题号 or '未命名'}
内容: {parsed_question.内容}
类型: {parsed_question.题型}
来源: {parsed_question.来源}
材料: {parsed_question.材料}
""".strip()

    # 生成向量嵌入
    embedding = embeddings.embed_query(content_to_embed)

    # 构建标签字符串
    tags_str = json.dumps([], ensure_ascii=False)  # 默认为空数组

    # 创建QuestionVector对象
    question_vector = QuestionVector(
        content=parsed_question.内容,
        embedding=embedding,
        title=f"题目 {parsed_question.题号}" if parsed_question.题号 else "导入题目",
        question_type=parsed_question.题型,
        difficulty=3,  # 默认中等难度
        source=parsed_question.来源,
        subject_id=subject_id,
        user_id=user_id,
        tags=tags_str,
        created_at=datetime.now().isoformat()
    )

    # 如果提供了数据库会话，保存到数据库
    if db:
        db.add(question_vector)
        await db.flush()  # 获取ID但不提交
        await db.refresh(question_vector)

    return question_vector

async def vectorize_questions_batch(
    parsed_questions: List[Question],
    user_id: int,
    subject_id: Optional[int] = None,
    db: AsyncSession = None
) -> List[QuestionVector]:
    """
    批量向量化试题

    Args:
        parsed_questions: 解析出的试题列表
        user_id: 用户ID
        subject_id: 学科ID（可选）
        db: 数据库会话

    Returns:
        List[QuestionVector]: 向量化的试题列表
    """
    question_vectors = []

    for parsed_question in parsed_questions:
        question_vector = await vectorize_question(
            parsed_question=parsed_question,
            user_id=user_id,
            subject_id=subject_id,
            db=db
        )
        question_vectors.append(question_vector)

    return question_vectors

async def search_similar_questions(
    query: str,
    user_id: int,
    subject_id: Optional[int] = None,
    limit: int = 10,
    db: AsyncSession = None
) -> List[QuestionVector]:
    """
    语义搜索相似试题

    Args:
        query: 搜索查询
        user_id: 用户ID
        subject_id: 学科ID（可选）
        limit: 返回结果数量
        db: 数据库会话

    Returns:
        List[QuestionVector]: 相似的试题列表
    """
    if not db:
        return []

    # 生成查询向量
    query_embedding = embeddings.embed_query(query)

    # 构建查询
    from sqlalchemy import text

    # 将向量转换为字符串格式
    embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

    # 使用pgvector的相似度搜索
    similarity_query = f"""
        SELECT id, content, title, question_type, difficulty, source, subject_id, user_id, tags, created_at,
               1 - (embedding <=> '{embedding_str}'::vector(1024)) as similarity
        FROM question_vectors
        WHERE user_id = {user_id}
        {"AND subject_id = " + str(subject_id) if subject_id is not None else ""}
        ORDER BY embedding <=> '{embedding_str}'::vector(1024)
        LIMIT {limit}
    """

    result = await db.execute(text(similarity_query))

    # 获取结果并转换为QuestionVector对象
    rows = result.fetchall()
    similar_questions = []

    for row in rows:
        # 创建QuestionVector对象（不包含embedding以节省内存）
        question_vector = QuestionVector(
            id=row[0],
            content=row[1],
            embedding=[],  # 不返回向量数据
            title=row[2],
            question_type=row[3],
            difficulty=row[4],
            source=row[5],
            subject_id=row[6],
            user_id=row[7],
            tags=row[8],
            created_at=row[9]
        )
        similar_questions.append(question_vector)

    return similar_questions
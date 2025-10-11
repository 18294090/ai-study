# app/schemas/question.py
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.question import QuestionStatus, QuestionType, ContentFormat

# --- 基础模型 ---
class QuestionBase(BaseModel):
    """问题模型的基础 Pydantic 模型"""
    title: str = Field(..., max_length=255, description="问题标题")
    content: str = Field(..., description="问题内容（题干）")
    content_format: ContentFormat = Field(ContentFormat.HTML, description="题干内容格式")
    type: QuestionType = Field(..., description="问题类型")
    difficulty: int = Field(..., ge=1, le=5, description="难度等级 (1-5)")
    subject_id: Optional[int] = Field(None, description="所属科目ID") 
    options: Optional[Dict[str, Any]] = Field(None, description="选项（针对选择题）")
    options_format: ContentFormat = Field(ContentFormat.HTML, description="选项内容格式")
    explanation: Optional[str] = Field(None, description="答案解析")
    explanation_format: ContentFormat = Field(ContentFormat.HTML, description="解析内容格式")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    source: Optional[str] = Field(None, max_length=255, description="题目来源")
    status: QuestionStatus = Field(default=QuestionStatus.DRAFT, description="题目状态")

# --- 用于创建的模型 ---
class QuestionCreate(QuestionBase):
    """用于创建问题的 Pydantic 模型"""
    # 确保answer字段类型一致
    answer: Dict[str, Any] = Field(..., description="正确答案，格式取决于题目类型")
    knowledge_point_ids: List[int] = Field(default_factory=list, description="知识点 ID 列表")
    source: Optional[str] = Field(None, max_length=255, description="题目来源")
    status: QuestionStatus = Field(default=QuestionStatus.DRAFT, description="题目状态")

# --- 用于更新的模型 ---
class QuestionUpdate(BaseModel):
    """用于更新问题的 Pydantic 模型（所有字段可选）"""
    title: Optional[str] = Field(None, max_length=255, description="问题标题")
    content: Optional[str] = Field(None, description="问题内容（题干）")
    content_format: Optional[ContentFormat] = Field(None, description="题干内容格式")
    type: Optional[QuestionType] = Field(None, description="问题类型")
    options: Optional[Dict[str, Any]] = Field(None, description="选项（针对选择题）")
    options_format: Optional[ContentFormat] = Field(None, description="选项内容格式")
    # 将 answer 与创建/响应保持一致，改为结构化对象
    answer: Optional[Dict[str, Any]] = Field(None, description="正确答案（结构化）")
    explanation: Optional[str] = Field(None, description="答案解析")
    explanation_format: Optional[ContentFormat] = Field(None, description="解析内容格式")
    difficulty: Optional[int] = Field(None, ge=1, le=5, description="难度等级 (1-5)")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    source: Optional[str] = Field(None, max_length=255, description="题目来源")
    status: Optional[QuestionStatus] = Field(None, description="题目状态")
    subject_id: Optional[int] = Field(None, description="学科 ID")
    knowledge_point_ids: Optional[List[int]] = Field(None, description="知识点 ID 列表")

# --- 用于响应的模型 ---
class QuestionResponse(QuestionBase):
    """用于 API 响应的 Pydantic 模型"""
    id: int
    author_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    answer: Dict[str, Any]  # 保持类型一致性
    # 调整为字典列表，匹配 Neo4j 返回
    knowledge_points: List[Dict[str, Any]] = Field(default_factory=list, description="知识点列表")
    source: Optional[str] = Field(None, max_length=255, description="题目来源")
    status: QuestionStatus
    model_config = ConfigDict(from_attributes=True)


# --- 添加以下内容 ---
class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    pass

class CommentResponse(CommentBase):
    id: int
    user_id: int
    question_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
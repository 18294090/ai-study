"""Core data structures and rules for exam parsing."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum

# Line text with bounding box
LineBBox = Tuple[str, Tuple[float, float, float, float]]

class QuestionType(str, Enum):
    """问题类型"""
    SINGLE_CHOICE = "single_choice"    # 单选题（包括判断题）
    MULTIPLE_CHOICE = "multiple_choice" # 多选题
    FILL_IN_BLANK = "fill_in_blank"    # 填空题
    SHORT_ANSWER = "short_answer"      # 简答题

@dataclass
class Question:
    """Represents a parsed question."""
    # 核心字段
    title: str = ""  # 问题标题
    content: str = ""  # 问题内容（题干）
    type: QuestionType = QuestionType.SINGLE_CHOICE  # 问题类型
    options: Optional[Dict[str, Any]] = None  # 选项（针对选择题）
    answer: Dict[str, Any] = field(default_factory=dict)  # 正确答案
    explanation: Optional[str] = None  # 答案解析
    
    # 教学信息
    difficulty: int = 3  # 难度等级 (1-5)
    tags: List[str] = field(default_factory=list)  # 标签列表
    subject_id: Optional[int] = None  # 所属科目ID
    
    # 管理信息
    source: str = ""  # 题目来源
    status: str = "draft"  # 题目状态
    
    # 旧字段（向后兼容）
    内容: str = ""
    来源: str = ""
    题型: str = "未知"
    配图: List[str] = field(default_factory=list)
    材料: str = ""
    题号: Optional[int] = None

    def __post_init__(self):
        # 向后兼容：如果旧字段有值，映射到新字段
        if self.内容 and not self.content:
            self.content = self.内容
        if self.来源 and not self.source:
            self.source = self.来源
        if self.题型 != "未知" and self.type == QuestionType.SINGLE_CHOICE:
            # 尝试映射题型
            if "单选" in self.题型:
                self.type = QuestionType.SINGLE_CHOICE
            elif "多选" in self.题型:
                self.type = QuestionType.MULTIPLE_CHOICE
            elif "填空" in self.题型:
                self.type = QuestionType.FILL_IN_BLANK
            elif "简答" in self.题型 or "问答" in self.题型:
                self.type = QuestionType.SHORT_ANSWER

    def to_csv_row(self) -> List[str]:
        return [
            self.content.rstrip("\r\n"), 
            self.type.value,
            self.source, 
            self.材料
        ]

    def to_dict(self) -> dict:
        return {
            "题目内容": self.content.rstrip("\r\n"),
            "题目类型": self.type.value,
            "来源": self.source,
            "材料": self.材料,
        }

    def to_question_create_dict(self) -> Dict[str, Any]:
        """转换为QuestionCreate格式的字典"""
        return {
            "title": self.title or self.content[:50] + "..." if len(self.content) > 50 else self.content,
            "content": self.content,
            "type": self.type.value,
            "options": self.options,
            "answer": self.answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "subject_id": self.subject_id,
            "source": self.source,
            "status": self.status,
            "knowledge_point_ids": []  # 可以后续扩展
        }
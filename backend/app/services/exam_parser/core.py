"""Core data structures and rules for exam parsing."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Line text with bounding box
LineBBox = Tuple[str, Tuple[float, float, float, float]]

@dataclass
class Question:
    """Represents a parsed question."""
    内容: str
    来源: str
    题型: str = "未知"
    配图: List[str] = field(default_factory=list)
    材料: str = ""
    题号: Optional[int] = None

    def to_csv_row(self) -> List[str]:
        return [
            self.内容.rstrip("\r\n"), 
            self.题型,
            self.来源, 
            self.材料
        ]

    def to_dict(self) -> dict:
        return {
            "题目内容": self.内容.rstrip("\r\n"),
            "题目类型": self.题型,
            "来源": self.来源,
            "材料": self.材料,
        }

    def to_question_create_dict(self) -> dict:
        """Convert parsed question to QuestionCreate dict format."""
        from app.models.question import QuestionType, ContentFormat, QuestionStatus
        
        # 映射题型
        type_mapping = {
            "单选题": QuestionType.SINGLE_CHOICE,
            "多选题": QuestionType.MULTIPLE_CHOICE,
            "填空题": QuestionType.FILL_IN_BLANK,
            "简答题": QuestionType.SHORT_ANSWER,
            "判断题": QuestionType.SINGLE_CHOICE,  # 判断题作为单选题处理
        }
        question_type = type_mapping.get(self.题型, QuestionType.SHORT_ANSWER)
        
        # 构建答案格式（这里需要根据题型推断，暂时使用默认值）
        if question_type == QuestionType.SINGLE_CHOICE:
            answer = {"type": "single", "value": "A"}  # 默认答案
        elif question_type == QuestionType.MULTIPLE_CHOICE:
            answer = {"type": "multiple", "value": ["A"]}  # 默认答案
        elif question_type == QuestionType.FILL_IN_BLANK:
            answer = {"type": "text", "value": [""]}  # 默认答案
        else:
            answer = {"type": "text", "value": ""}  # 默认答案
        return {
            "title": f"题目 {self.题号}" if self.题号 else "导入题目",
            "content": self.内容,
            "content_format": ContentFormat.HTML,
            "type": question_type,
            "difficulty": 3,  # 默认中等难度
            "options": None,  # 暂时不支持选项解析
            "options_format": ContentFormat.HTML,
            "answer": answer,
            "explanation": None,  # 暂时不支持解析解析
            "explanation_format": ContentFormat.HTML,
            "tags": [],  # 空标签列表，避免null值
            "source": self.来源,
            "status": QuestionStatus.DRAFT,
            "knowledge_point_ids": []  # 空知识点ID列表
        }
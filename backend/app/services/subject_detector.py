"""Auto-detect subject and grade level from textbook content using LLM."""

from typing import Tuple, Optional
import json

from app.kg.src.llm_router import LLMRouter
from app.kg.src.config import get_config


SUBJECT_CATEGORIES = [
    "语文", "数学", "英语", "物理", "化学", "生物",
    "历史", "地理", "政治", "道德与法治", "信息技术",
    "音乐", "美术", "体育", "科学", "思想政治",
]

GRADE_LEVELS = ["小学", "初中", "高中", "大学", "研究生"]


async def detect_subject_and_grade(textbook_title: str, first_chapter_content: str) -> Tuple[str, Optional[str]]:
    """Detect subject and grade level from textbook content.

    Args:
        textbook_title: Title of the textbook
        first_chapter_content: Content from the first chapter

    Returns:
        Tuple of (subject_name, grade_level)
    """
    sample_text = first_chapter_content[:2000] if first_chapter_content else textbook_title

    prompt = f"""分析以下教材，判断其学科和学段。

教材标题: {textbook_title}

内容样本:
{sample_text}

请以JSON格式返回分析结果:
{{
    "subject": "学科名称",
    "grade_level": "学段 (小学/初中/高中/大学/研究生)",
    "confidence": 0.0-1.0
}}

只返回一个JSON对象，不要有其他内容。"""

    try:
        cfg = get_config()
        router = LLMRouter()
        client = router.get_client()

        response = client.invoke(prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        data = json.loads(content.strip())
        subject = data.get("subject", "未知")
        grade_level = data.get("grade_level")

        return subject, grade_level

    except Exception as e:
        print(f"[subject_detector] LLM error: {e}")
        return "未知", None


def extract_textbook_info(markdown: str) -> Tuple[str, str]:
    """Extract title and first chapter content from markdown.

    Args:
        markdown: Markdown content from MinerU

    Returns:
        Tuple of (title, first_chapter_content)
    """
    lines = markdown.split("\n")

    title = ""
    first_content = []
    in_first_chapter = False

    for line in lines:
        if not title and line.startswith("# "):
            title = line[2:].strip()
            in_first_chapter = True
            continue

        if in_first_chapter:
            if line.startswith("# ") and len(first_content) > 0:
                break
            first_content.append(line)

    first_chapter_content = "\n".join(first_content[:50])
    return title or "未知教材", first_chapter_content
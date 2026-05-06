"""Extract entities tool for Hermes."""

from typing import Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    id: str
    name: str
    type: str
    properties: Dict[str, Any]
    confidence: float


def extract_entities(source: str, source_type: str = "text", subject_id: int = None) -> Dict[str, Any]:
    """Extract entities from source text or document.

    Args:
        source: Text content or file path
        source_type: Type of source (text, pdf, markdown)
        subject_id: Optional subject ID for context

    Returns:
        Dict with entities list and confidence score
    """
    try:
        from app.kg.src.llm_router import LLMRouter

        prompt = f"""从以下内容中提取知识图谱实体，返回JSON格式:

内容类型: {source_type}
内容: {source[:5000]}

返回格式:
{{
    "entities": [
        {{"name": "实体名称", "type": "实体类型", "properties": {{}}, "confidence": 0.0-1.0}}
    ],
    "confidence": 平均置信度
}}"""

        router = LLMRouter()
        client = router.get_client()
        response = client.invoke(prompt)

        content = response.content if hasattr(response, 'content') else str(response)

        import json
        result = json.loads(content)

        return {
            "success": True,
            "entities": result.get("entities", []),
            "confidence": result.get("confidence", 0.0),
            "count": len(result.get("entities", []))
        }
    except Exception as e:
        logger.error(f"extract_entities failed: {e}")
        return {"success": False, "error": str(e), "entities": []}
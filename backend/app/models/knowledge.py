"""向后兼容的知识点模块。

系统已经将知识点相关模型迁移到 ``app.models.knowledge_point`` 中。
为避免大规模修改旧代码，本模块仅导出该文件中的模型，
新功能请直接引用 ``app.models.knowledge_point``。
"""

from app.models.knowledge_point import (  # noqa: F401
    KnowledgePoint,
    KnowledgePointVersion,
    KnowledgePointRelationship,
    KnowledgePointAuditLog,
    TextbookVersion,
    TextbookMapping,
    knowledge_point_textbook_version,
    knowledge_point_closure,
)

__all__ = [
    "KnowledgePoint",
    "KnowledgePointVersion",
    "KnowledgePointRelationship",
    "KnowledgePointAuditLog",
    "TextbookVersion",
    "TextbookMapping",
    "knowledge_point_textbook_version",
    "knowledge_point_closure",
]


from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from app.models.base import Base
from datetime import datetime
import enum

class ResourceType(str, enum.Enum):
    ARTICLE = "article"
    VIDEO = "video"
    DOCUMENT = "document"
    WEBSITE = "website"
    TOOL = "tool"
    OTHER = "other"

class Resource(Base):
    __tablename__ = "resources"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(500), nullable=False)
    resource_type = Column(SQLAlchemyEnum(ResourceType), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 上传者ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    knowledge_point = relationship("KnowledgePoint", back_populates="resources")
    user = relationship("User", backref="uploaded_resources")  # 上传者关系

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from app.models.base import Base

class OperationLog(Base):
    """
    操作日志模型，用于记录用户的重要操作。
    """
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 操作用户，可能为None（如系统操作）
    operation = Column(String(100), nullable=False)  # 操作类型，如 "create_question", "login"
    path = Column(String(255))  # 请求路径
    method = Column(String(10))  # HTTP方法
    ip_address = Column(String(50))  # 用户IP地址
    details = Column(String(500), nullable=True)  # 操作详情

    user = relationship("User")

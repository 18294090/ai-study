"""用户模型
定义用户相关的数据库模型，包括：
- 基本用户信息
- 认证相关字段
- 权限控制
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Boolean, String, DateTime, Integer, ForeignKey, Table, Column, JSON, Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from enum import Enum
# 导入密码处理函数
from app.core.password import get_password_hash
# 导入已定义的关联表
from app.models.subject import user_subject
from app.models.assignment import UserAssignment
from app.models.class_model import class_student

if TYPE_CHECKING:
    from app.models.class_model import Class
    from app.models.question import Question

def _load_knowledge_point():
    from app.models.knowledge import KnowledgePoint
    return KnowledgePoint

def _load_tag():
    from app.models.subject import Tag
    return Tag


# 修正表名引用
user_role_table = Table(
    "user_role",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permission_table = Table(
    "role_permission",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

class UserRole(str, Enum):
    """用户角色枚举"""
    STUDENT = "student"    # 学生
    ADMIN = "admin"      # 管理员

class User(Base):
    """用户模型"""
    __tablename__ = "users"
    __mapper_args__ = {
        'polymorphic_on': 'user_type',
        'polymorphic_identity': 'user'
    }
    __table_args__ = {'extend_existing': True}    
    # 基本信息
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    # Add the missing user_type column
    user_type: Mapped[str] = mapped_column(String(50), default='user')
    # 教师的科目列表，重命名为 subject_list 避免与关系属性冲突
    subject_list: Mapped[List[dict]] = mapped_column(
        JSON, 
        default=list,
        nullable=True,
        info={
            'example': [
                {'id': 'math', 'name': '数学'},
                {'id': 'physics', 'name': '物理'}
            ]
        }
    )    
    # 认证相关
    hashed_password: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 额外信息
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    avatar: Mapped[Optional[str]] = mapped_column(String(200))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SQLAlchemyEnum(UserRole),
        default=UserRole.STUDENT,  # 设置默认角色为STUDENT
        nullable=False
    )

    # 关系
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary=user_role_table,
        back_populates="users"
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        back_populates="author",
        cascade="all, delete-orphan"
    )
    comments = relationship("QuestionComment", back_populates="user")
   

    # 关联关系
    subjects = relationship("Subject", secondary=user_subject, back_populates="teachers")
    # 知识点关系
    created_knowledge_points = relationship(_load_knowledge_point, back_populates="creator")
    # 添加这两个关系属性
    teaching_classes = relationship(
        "Class", 
        back_populates="teacher",
        foreign_keys="Class.teacher_id"
    )
    created_tags = relationship(_load_tag, back_populates="creator")
    enrolled_classes = relationship(
        "Class",
        secondary=class_student,  # 使用导入的 class_student
        back_populates="students"
    )

    # 添加作业相关关系
    created_assignments = relationship(
        "Assignment", 
        back_populates="creator",
        foreign_keys="Assignment.creator_id"
    )
    
    user_assignments = relationship(
        UserAssignment,
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        """字符串表示"""
        return f"User(id={self.id}, username={self.username})"
    
    def set_password(self, password: str) -> None:
        """设置密码

        Args:
            password: 明文密码
        """
        self.hashed_password = get_password_hash(password)
    
    @property
    def is_admin(self) -> bool:
        """是否是管理员"""
        return self.is_superuser or any(role.name == "admin" for role in self.roles)
    
    def has_role(self, role_name: str) -> bool:
        """检查是否有指定角色
        
        Args:
            role_name: 角色名称
            
        Returns:
            bool: 是否具有该角色
        """
        return any(role.name == role_name for role in self.roles)
    
    def has_permission(self, permission: str) -> bool:
        """检查是否有指定权限
        
        Args:
            permission: 权限标识
            
        Returns:
            bool: 是否具有该权限
        """
        if self.is_superuser:
            return True
        return any(
            any(p.name == permission for p in role.permissions)
            for role in self.roles
        )

class Role(Base):
    """角色模型"""
    __tablename__ = "roles"  # 添加表名
    
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(200))    
    # 关系
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary=role_permission_table,
        back_populates="roles"
    )
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_role_table,
        back_populates="roles"
    )

class Permission(Base):
    """权限模型"""    
    __tablename__ = "permissions"  # 添加表名
    
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(200))    
    # 关系
    roles: Mapped[List[Role]] = relationship(
        Role,
        secondary=role_permission_table,
        back_populates="permissions"
    )
    
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(200))    
    # 关系
    roles: Mapped[List[Role]] = relationship(
        Role,
        secondary=role_permission_table,
        back_populates="permissions"
    )


"""
知识点体系管理数据模型

设计理念: 采用"实体-关系-属性"三元组图结构
- 核心实体: KnowledgePoint, Subject, TextbookVersion, Relationship
- 版本控制: 完整的版本历史记录
- 扩展性: 键值对(Key-Value)结构支持自定义属性
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Column, String, Integer, Float, Text, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum, JSON, Table, UniqueConstraint,
    Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, relationship, mapped_column

from app.models.base import Base
from app.models.question import question_knowledge_point

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.question import Question
    from app.models.resource import Resource
    from app.models.user import User
    from app.models.subject import Subject


# ======================== Enum定义 ========================

class DifficultyLevel(int, Enum):
    """难度等级: 1-5级"""
    VERY_EASY = 1      # 非常简单
    EASY = 2            # 简单
    MEDIUM = 3          # 中等
    HARD = 4            # 困难
    VERY_HARD = 5       # 非常困难


class TeachingRequirement(str, Enum):
    """教学要求"""
    UNDERSTAND = "了解"        # 了解基本概念
    COMPREHEND = "理解"        # 理解原理和方法
    MASTER = "掌握"            # 掌握并能应用
    APPLY = "应用"             # 能够灵活应用


class ExamFrequency(str, Enum):
    """考查频率"""
    LOW = "低频"        # 低频考查
    MEDIUM = "中频"      # 中频考查
    HIGH = "高频"        # 高频考查
    VERY_HIGH = "超高频"  # 超高频考查


class RelationshipType(str, Enum):
    """知识点关系类型"""
    # 层次关系
    CONTAINS = "contains"           # A包含B
    COMPOSED_OF = "composed_of"     # A由B组成
    
    # 依赖关系
    PREREQUISITE = "prerequisite"   # A是B的前置知识
    DEPENDS_ON = "depends_on"       # A依赖于B
    
    # 应用关系
    APPLIES_TO = "applies_to"       # A应用于B
    APPLIED_BY = "applied_by"       # A被B应用
    
    # 关联关系
    RELATED_TO = "related_to"       # A与B相关
    SIMILAR_TO = "similar_to"       # A与B相似
    
    # 跨学科关系
    THEORY_SUPPORTS = "theory_supports"      # 理论支撑
    METHOD_BORROWS = "method_borrows"        # 方法借鉴
    CROSS_DISCIPLINE = "cross_discipline"    # 交叉融合


class VersionStatus(str, Enum):
    """版本状态"""
    DRAFT = "draft"              # 草稿
    PENDING_REVIEW = "pending"   # 待审核
    APPROVED = "approved"        # 已批准
    PUBLISHED = "published"      # 已发布
    ARCHIVED = "archived"        # 已归档
    DELETED = "deleted"          # 已删除


# ======================== 关联表 ========================

# 知识点与教材版本的关联表(多对多)
knowledge_point_textbook_version = Table(
    'knowledge_point_textbook_version',
    Base.metadata,
    Column('knowledge_point_id', Integer, ForeignKey('knowledge_points.id', ondelete="CASCADE"), primary_key=True),
    Column('textbook_version_id', Integer, ForeignKey('textbook_versions.id', ondelete="CASCADE"), primary_key=True),
    Column('position', String(255), nullable=True, comment="在教材中的位置(如:第七年级下册第三章第二节)"),
    Column('created_at', DateTime, default=datetime.utcnow),
)

# 知识点闭包表，用于快速查询祖先/后代关系
knowledge_point_closure = Table(
    'knowledge_point_closure',
    Base.metadata,
    Column('ancestor_id', Integer, ForeignKey('knowledge_points.id', ondelete="CASCADE"), primary_key=True),
    Column('descendant_id', Integer, ForeignKey('knowledge_points.id', ondelete="CASCADE"), primary_key=True),
    Column('depth', Integer, nullable=False, default=0),
    Index('idx_kpc_ancestor', 'ancestor_id'),
    Index('idx_kpc_descendant', 'descendant_id'),
)

# ======================== 核心模型 ========================


class TextbookVersion(Base):
    """
    教材版本模型
    
    记录人教版、苏教版等不同版本的教材信息
    """
    __tablename__ = "textbook_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="教材版本代码")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="教材版本名称")
    publisher: Mapped[str] = mapped_column(String(100), nullable=False, comment="出版社")
    
    # 版本信息
    version_number: Mapped[str] = mapped_column(String(50), nullable=False, comment="版本号(如:2024年版)")
    publication_year: Mapped[int] = mapped_column(Integer, nullable=False, comment="出版年份")
    
    # 适用范围
    applicable_grades: Mapped[List[str]] = mapped_column(JSON, nullable=False, comment="适用学段(JSON数组)")
    applicable_subjects: Mapped[List[str]] = mapped_column(JSON, nullable=False, comment="涵盖学科(JSON数组)")
    applicable_regions: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, comment="适用地区")
    
    # 描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="版本描述")
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    
    # 元数据
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="自定义属性")

    # 关系
    knowledge_points: Mapped[List["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        secondary=knowledge_point_textbook_version,
        back_populates="textbook_versions"
    )
    textbook_mappings: Mapped[List["TextbookMapping"]] = relationship(
        "TextbookMapping",
        back_populates="textbook_version",
        cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_textbook_code', 'code'),
        Index('idx_textbook_name', 'name'),
    )


class KnowledgePoint(Base):
    """
    知识点模型(核心)
    
    代表某个具体的知识点，如"一元二次方程"、"光合作用"等
    设计为支持版本控制和多版本教材映射
    """
    __tablename__ = "knowledge_points"
    
    # 唯一标识
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, 
                                      comment="知识点编码(格式:学科代码-学段代码-序号)")
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True,
                                     comment="URL友好的标识符")
    
    # 基本信息
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="知识点名称")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="知识点描述")
    
    # 分类信息
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, comment="所属学科ID")
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="领域(如:数与代数)")
    topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="主题(如:函数)")
    grade_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, 
                                            comment="学段(如:初中三年级)")
    
    # 难度和要求
    difficulty: Mapped[int] = mapped_column(Integer, default=DifficultyLevel.MEDIUM,
                                           comment="难度等级(1-5)")
    teaching_requirement: Mapped[TeachingRequirement] = mapped_column(
        SQLEnum(TeachingRequirement),
        default=TeachingRequirement.MASTER,
        comment="教学要求"
    )
    exam_frequency: Mapped[ExamFrequency] = mapped_column(
        SQLEnum(ExamFrequency),
        default=ExamFrequency.MEDIUM,
        comment="考查频率"
    )
    
    # 教学属性
    learning_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
                                                            comment="学习时长(分钟)")
    is_key_point: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为重点知识点")
    is_difficulty_point: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为难点")
    is_error_prone: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否易错")
    
    # 层级结构
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("knowledge_points.id"), 
                                                    nullable=True, comment="父知识点ID")
    depth: Mapped[int] = mapped_column(Integer, default=1, comment="知识点深度(用于快速查询)")
    path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, comment="层级路径(如 1/3/5)")
    
    # 状态和版本
    status: Mapped[VersionStatus] = mapped_column(
        SQLEnum(VersionStatus),
        default=VersionStatus.PUBLISHED,
        comment="知识点状态"
    )
    version: Mapped[str] = mapped_column(String(50), default="v1.0.0", comment="当前版本号")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    
    # 元数据和权重
    weight: Mapped[float] = mapped_column(Float, default=1.0, comment="知识点权重")
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True, comment="知识点标签")
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True,
                                                               comment="自定义属性")
    
    # 创建者
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, comment="创建者ID")
    creator: Mapped["User"] = relationship("User", back_populates="created_knowledge_points")

    # 审计信息
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="创建人")
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="修改人")
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="审核人")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="审核时间")
    
    # 关系
    subject: Mapped["Subject"] = relationship("Subject", back_populates="knowledge_points")
    
    # 自引用关系(父子知识点)
    children: Mapped[List["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        back_populates="parent",
        foreign_keys="KnowledgePoint.parent_id",
        cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["KnowledgePoint"]] = relationship(
        "KnowledgePoint",
        back_populates="children",
        foreign_keys="KnowledgePoint.parent_id",
        remote_side="KnowledgePoint.id"
    )
    
    # 版本历史
    versions: Mapped[List["KnowledgePointVersion"]] = relationship(
        back_populates="knowledge_point",
        cascade="all, delete-orphan"
    )

    # 其他关系
    relationships_from: Mapped[List["KnowledgePointRelationship"]] = relationship(
        back_populates="source",
        foreign_keys="KnowledgePointRelationship.source_id",
        cascade="all, delete-orphan"
    )
    relationships_to: Mapped[List["KnowledgePointRelationship"]] = relationship(
        back_populates="target",
        foreign_keys="KnowledgePointRelationship.target_id",
        cascade="all, delete-orphan"
    )
    textbook_versions: Mapped[List["TextbookVersion"]] = relationship(
        secondary=knowledge_point_textbook_version,
        back_populates="knowledge_points"
    )
    textbook_mappings: Mapped[List["TextbookMapping"]] = relationship(
        back_populates="knowledge_point",
        cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["KnowledgePointAuditLog"]] = relationship(
        back_populates="knowledge_point",
        cascade="all, delete-orphan"
    )

    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment",
        back_populates="knowledge_point"
    )
    resources: Mapped[List["Resource"]] = relationship(
        "Resource",
        back_populates="knowledge_point",
        cascade="all, delete-orphan"
    )
    questions: Mapped[List["Question"]] = relationship(
        "Question",
        secondary=question_knowledge_point,
        back_populates="knowledge_points",
        lazy="selectin"
    )
    
    __table_args__ = (
        Index('idx_kp_code', 'code'),
        Index('idx_kp_slug', 'slug'),
        Index('idx_kp_name', 'name'),
        Index('idx_kp_subject_id', 'subject_id'),
        Index('idx_kp_status', 'status'),
        Index('idx_kp_grade_level', 'grade_level'),
        UniqueConstraint('subject_id', 'name', name='uq_kp_subject_name'),
        CheckConstraint('difficulty >= 1 AND difficulty <= 5', name='check_difficulty_range'),
    )


class KnowledgePointVersion(Base):
    """
    知识点版本历史模型
    
    记录知识点的每次变更，支持版本回溯和变更追踪
    """
    __tablename__ = "knowledge_point_versions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 关联信息
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), 
                                                   nullable=False, comment="知识点ID")
    
    # 版本信息
    version_number: Mapped[str] = mapped_column(String(50), nullable=False, comment="版本号(v1.0.0格式)")
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, 
                                            comment="变更类型(create/update/delete)")
    change_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                             comment="变更描述")
    
    # 变更内容(JSON格式记录变更前后)
    previous_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True,
                                                                   comment="变更前的数据")
    current_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True,
                                                                  comment="变更后的数据")
    
    # 操作人信息
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False, comment="操作人")
    change_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True,
                                                        comment="变更原因")
    
    # 审核信息
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="审核人")
    review_status: Mapped[str] = mapped_column(String(20), default="pending", 
                                              comment="审核状态(pending/approved/rejected)")
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="审核意见")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="审核时间")
    
    # 关系
    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="versions")
    
    __table_args__ = (
        Index('idx_kpv_knowledge_point_id', 'knowledge_point_id'),
        Index('idx_kpv_version_number', 'version_number'),
        Index('idx_kpv_created_at', 'created_at'),
    )


class KnowledgePointRelationship(Base):
    """知识点关系模型"""

    __tablename__ = "knowledge_point_relationships"
    source_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id"), nullable=False, comment="源知识点ID"
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id"), nullable=False, comment="目标知识点ID"
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SQLEnum(RelationshipType), nullable=False, comment="关系类型"
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0, comment="关系权重(0-1)")
    intensity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="关系强度")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="关系描述")
    application_scenario: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="应用场景")
    teaching_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="教学建议")
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="自定义属性")
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已验证")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")

    source: Mapped[KnowledgePoint] = relationship(
        "KnowledgePoint", back_populates="relationships_from", foreign_keys=[source_id]
    )
    target: Mapped[KnowledgePoint] = relationship(
        "KnowledgePoint", back_populates="relationships_to", foreign_keys=[target_id]
    )

    __table_args__ = (
        Index('idx_kpr_source_id', 'source_id'),
        Index('idx_kpr_target_id', 'target_id'),
        Index('idx_kpr_relationship_type', 'relationship_type'),
        UniqueConstraint('source_id', 'target_id', 'relationship_type', name='uq_kpr_source_target_type'),
    )


class TextbookMapping(Base):
    """
    知识点与教材版本的映射模型
    
    记录同一知识点在不同教材版本中的具体位置和表现形式
    """
    __tablename__ = "textbook_mappings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # 关联信息
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"),
                                                   nullable=False, comment="知识点ID")
    textbook_version_id: Mapped[int] = mapped_column(ForeignKey("textbook_versions.id"),
                                                    nullable=False, comment="教材版本ID")
    
    # 位置信息
    book_title: Mapped[str] = mapped_column(String(200), nullable=False, comment="册号名称")
    chapter: Mapped[int] = mapped_column(Integer, nullable=False, comment="章号")
    section: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="节号")
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="单元")
    
    # 呈现形式
    presentation_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True,
                                                            comment="在该版本中的知识点名称")
    presentation_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                                   comment="呈现方式描述")
    
    # 难度差异
    difficulty_adjustment: Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
                                                                comment="难度调整(相对于标准难度)")
    
    # 内容差异
    content_variation: Mapped[Optional[str]] = mapped_column(Text, nullable=True,
                                                            comment="内容差异分析")
    examples_count: Mapped[int] = mapped_column(Integer, default=0, comment="例题数量")
    exercises_count: Mapped[int] = mapped_column(Integer, default=0, comment="练习数量")
    
    # 元数据
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True,
                                                               comment="自定义属性")
    
    # 审核状态
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已验证")
    verified_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, 
                                                      comment="验证人")
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True,
                                                           comment="验证时间")
    
    # 关系
    knowledge_point: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint",
        back_populates="textbook_mappings"
    )
    textbook_version: Mapped["TextbookVersion"] = relationship(
        "TextbookVersion",
        back_populates="textbook_mappings"
    )
    
    __table_args__ = (
        Index('idx_tm_knowledge_point_id', 'knowledge_point_id'),
        Index('idx_tm_textbook_version_id', 'textbook_version_id'),
        UniqueConstraint('knowledge_point_id', 'textbook_version_id',
                        name='uq_tm_kp_textbook'),
    )


class KnowledgePointAuditLog(Base):
    """
    知识点审核日志模型
    
    记录知识点的审核流程和决策
    """
    __tablename__ = "knowledge_point_audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)    
    # 关联信息
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"),
                                                   nullable=False, comment="知识点ID")
    
    # 审核流程
    stage: Mapped[str] = mapped_column(String(50), nullable=False, 
                                      comment="审核阶段(初审/复审/终审)")
    reviewer_id: Mapped[str] = mapped_column(String(100), nullable=False, comment="审核人ID")
    reviewer_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="审核人名称")
    
    # 审核结果
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                       comment="审核状态(pending/approved/rejected)")
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="审核意见")
    
    # 审核数据
    reviewed_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True,
                                                                   comment="审核时的数据快照")
    
    # 关系
    knowledge_point: Mapped["KnowledgePoint"] = relationship(
        "KnowledgePoint",
        back_populates="audit_logs"
    )
    
    __table_args__ = (
        Index('idx_kpal_knowledge_point_id', 'knowledge_point_id'),
        Index('idx_kpal_stage', 'stage'),
        Index('idx_kpal_status', 'status'),
    )

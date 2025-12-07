# 导入顺序很重要，先导入不依赖其他模型的基础模型
from app.models.base import Base
# 导入用户相关模型
from app.models.user import User
# 导入学科模型
from app.models.subject import Subject
# 导入书籍模型
from app.models.book import Book
# 导入知识点模型
from app.models.knowledge import KnowledgePoint
# 导入向量存储模型
from app.models.VectorStore import DocumentChunk, QuestionVector
# 导入知识点和相关资源模型
from app.models.resource import Resource
# 导入题目相关模型
from app.models.question import Question, QuestionComment

# 导入班级和作业相关模型
from app.models.class_model import Class  # 重命名避免与Python关键字冲突
from app.models.assignment import Assignment

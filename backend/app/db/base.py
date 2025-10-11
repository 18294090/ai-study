# Import all models to ensure they are registered with SQLAlchemy

from app.models.base import Base
from app.models.user import User
from app.models.subject import Subject
from app.models.question import Question, QuestionComment
# 导入其他模型...

# 这个文件的目的是确保所有模型都被导入，
# 这样SQLAlchemy才能在数据库迁移或创建表时找到它们

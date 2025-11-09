# 具体的Celery任务定义
from app.tasks.celery_tasks import celery_app
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.core.config import settings
from app.models.question import Question
from app.services.exam_parser import parse_pdf, parse_docx, parse_image
from typing import Optional
import tempfile
import os
import shutil

# 创建同步数据库引擎（用于Celery任务）
sync_engine = create_engine(
    str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://"),
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

@celery_app.task(bind=True)
def process_file_import_task(self, file_path: str, file_type: str, user_id: int, subject_id: Optional[int] = None):
    """Celery任务：处理文件导入"""

    img_dir = None
    db = None
    try:
        # 更新任务状态
        self.update_state(state='PROGRESS', meta={'message': f'开始处理 {file_type} 文件'})

        # 创建临时图片目录
        img_dir = tempfile.mkdtemp(prefix="exam_parser_")

        # 根据文件类型调用相应的解析器
        if file_type == 'pdf':
            questions = parse_pdf(file_path, img_dir)
        elif file_type in ['docx', 'doc']:
            questions = parse_docx(file_path, img_dir)
        elif file_type in ['png', 'jpg', 'jpeg']:
            questions = parse_image(file_path, img_dir)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # 获取数据库会话
        db = SyncSessionLocal()

        # 将解析的题目存储到数据库
        created_questions = []
        for parsed_question in questions:
            # 转换为QuestionCreate格式
            question_data = parsed_question.to_question_create_dict()
            question_data['author_id'] = user_id
            if subject_id:
                question_data['subject_id'] = subject_id

            # 创建题目对象
            db_question = Question(**question_data)
            db.add(db_question)
            created_questions.append(db_question)

        db.commit()

        # 刷新所有创建的题目
        for q in created_questions:
            db.refresh(q)

        return {
            'status': 'SUCCESS',
            'message': f'成功导入 {len(created_questions)} 道题目',
            'created_count': len(created_questions)
        }

    except Exception as e:
        if db:
            db.rollback()
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        # 清理数据库会话
        if db:
            db.close()
        # 清理临时文件和目录
        if os.path.exists(file_path):
            os.remove(file_path)
        if img_dir and os.path.exists(img_dir):
            shutil.rmtree(img_dir)
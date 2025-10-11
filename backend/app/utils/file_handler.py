import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from PIL import Image

from app.core.config import settings
import io

class FileHandler:
    UPLOAD_DIR = settings.UPLOAD_DIR
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif"}
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

    @classmethod
    async def save_upload_file(cls, file: UploadFile) -> Optional[str]:
        try:
            # 验证文件类型
            if file.content_type not in cls.ALLOWED_IMAGE_TYPES:
                return None

            # 创建上传目录
            upload_dir = Path(cls.UPLOAD_DIR)
            if not upload_dir.exists():
                upload_dir.mkdir(parents=True)

            # 生成唯一文件名
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # 按年月组织文件夹
            today = datetime.now()
            year_month = today.strftime("%Y%m")
            save_dir = upload_dir / year_month
            if not save_dir.exists():
                save_dir.mkdir(parents=True)

            file_path = save_dir / unique_filename
            
            # 读取和保存文件
            contents = await file.read()
            if len(contents) > cls.MAX_IMAGE_SIZE:
                return None

            # 写入文件
            with open(file_path, "wb") as f:
                f.write(contents)

            # 验证是否为有效图片
            try:
                with Image.open(file_path) as img:
                    img.verify()
            except Exception:
                if file_path.exists():
                    file_path.unlink()  # 删除无效的文件
                return None
            with open(file_path, "wb") as f:
                f.write(contents)

            # 返回相对路径
            return f"{cls.UPLOAD_DIR}/{year_month}/{unique_filename}"

        except Exception as e:
            print(f"Error saving file: {str(e)}")
            return None

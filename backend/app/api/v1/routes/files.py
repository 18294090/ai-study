from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
import aiofiles
import os
from app.core.config import settings
from app.core.auth import get_current_user
import uuid

router = APIRouter()

@router.post("/upload", operation_id="文件上传")
async def upload_files(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    current_user = Depends(get_current_user)
):
    """上传文件（兼容字段名 file 与 files）"""
    all_files: List[UploadFile] = []
    if file is not None:
        all_files.append(file)
    if files:
        all_files.extend(files)

    if not all_files:
        raise HTTPException(status_code=422, detail="No files uploaded")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    results = []
    for f in all_files:
        try:
            _, ext = os.path.splitext(f.filename or '')
            if not ext:
                ext = '.bin'
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            async with aiofiles.open(file_path, 'wb') as out:
                content = await f.read()
                await out.write(content)
            # 提供可用于前端展示的URL（按实际静态挂载路径调整）
            public_url = f"/uploads/{unique_filename}"
            results.append({
                "filename": f.filename,
                "saved_as": unique_filename,
                "file_path": file_path,
                "url": public_url
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload file {f.filename}: {str(e)}")

    # 同时返回第一个文件的url，便于前端直接取值
    return {"url": results[0]["url"], "files": results}

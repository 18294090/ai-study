"""Hermes HTTP gateway routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import Optional
import tempfile
import os
from pydantic import BaseModel

from .runtime import HermesRuntime
from .skills.exam_skill import run_exam_skill
from app.core.auth import get_current_user
from app.models.user import User


router = APIRouter(prefix="/hermes", tags=["hermes"])


class ExamExtractRequest(BaseModel):
    file_path: str
    confidence_threshold: Optional[float] = 0.6
    source: Optional[str] = None


@router.post("/exam/extract")
async def extract_exam(
    request: ExamExtractRequest,
    current_user: User = Depends(get_current_user)
):
    """Extract questions from exam PDF using Hermes skill."""
    result = await run_exam_skill({
        "file_path": request.file_path,
        "confidence_threshold": request.confidence_threshold,
        "source": request.source,
    })

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Extraction failed"))

    return result


@router.post("/exam/upload")
async def upload_and_extract_exam(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.6,
    current_user: User = Depends(get_current_user)
):
    """Upload PDF and extract questions."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)

    try:
        await file.seek(0)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        result = await run_exam_skill({
            "file_path": file_path,
            "confidence_threshold": confidence_threshold,
        })

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Extraction failed"))

        return result

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rmdir(temp_dir)


@router.get("/health")
async def hermes_health():
    """Health check for Hermes runtime."""
    return {"status": "ok", "runtime": "hermes", "version": "1.0.0"}
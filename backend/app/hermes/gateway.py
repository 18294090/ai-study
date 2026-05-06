"""Hermes HTTP gateway routes."""

import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import Optional
import tempfile
import os
from pydantic import BaseModel

from .skills.exam_skill import run_exam_skill
from app.core.auth import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
VERSION = "1.0.0"

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
    logger.info(f"Extract exam request for file: {request.file_path}")
    try:
        result = await run_exam_skill({
            "file_path": request.file_path,
            "confidence_threshold": request.confidence_threshold,
            "source": request.source,
        })
    except Exception as e:
        logger.error(f"Error running exam skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

        logger.info(f"Processing uploaded file: {file.filename}")
        try:
            result = await run_exam_skill({
                "file_path": file_path,
                "confidence_threshold": confidence_threshold,
            })
        except Exception as e:
            logger.error(f"Error running exam skill: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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
    return {"status": "ok", "runtime": "hermes", "version": VERSION}
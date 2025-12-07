from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.application import ApplicationStatus

class SubjectApplicationBase(BaseModel):
    subject_id: int
    applicant_id: int
    message: Optional[str] = None

class SubjectApplicationCreate(SubjectApplicationBase):
    pass

class SubjectApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    message: Optional[str] = None

class SubjectApplication(SubjectApplicationBase):
    id: int
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ClassApplicationBase(BaseModel):
    class_id: int
    applicant_id: int
    message: Optional[str] = None

class ClassApplicationCreate(ClassApplicationBase):
    pass

class ClassApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    message: Optional[str] = None

class ClassApplication(ClassApplicationBase):
    id: int
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 通用更新schema
class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    message: Optional[str] = None
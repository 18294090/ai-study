from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum

from app.models.user import UserRole

class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    role: UserRole = UserRole.TEACHER  # 设置默认角色

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None
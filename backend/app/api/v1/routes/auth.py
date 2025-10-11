from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.password import verify_password, get_password_hash
from app.core.security import create_access_token
from app.models.user import User, UserRole  # 确保导入UserRole
from app.schemas.user import Token, UserCreate, UserResponse  # <-- 修改这里
from typing import List
from datetime import datetime
from app.dependencies.auth import get_current_user

router = APIRouter()

async def authenticate_user(username: str, password: str, db: AsyncSession,operation_id="用户验证") -> User | None:
    """验证用户凭据，支持用户名或邮箱登录"""
    query = select(User).where(
        (User.email == username) | (User.username == username)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED,operation_id="用户注册")
async def register(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 检查邮箱是否已存在
    query = select(User).filter(User.email == user_create.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # 创建新用户，默认使用STUDENT角色
    db_user = User(
        email=user_create.email,
        username=user_create.username,
        hashed_password=get_password_hash(user_create.password),
        role=UserRole.STUDENT  # 使用STUDENT作为默认角色
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token,operation_id="用户登录")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    user = await authenticate_user(form_data.username, form_data.password, db)    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    await db.commit()
    
    access_token = create_access_token(subject=user.id, scopes=[user.role.value])
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse,operation_id="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user
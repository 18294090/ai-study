"""
安全相关功能模块

包含:
- JWT token 的创建和验证
- 安全中间件配置
- 权限验证装饰器
"""
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional, Union, List, cast
from fastapi import Depends, FastAPI, HTTPException, Security, status, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
# 导入密码相关函数从新模块
from app.core.password import verify_password, get_password_hash
from app.models.user import User

logger = get_logger(__name__)

# 在函数内部导入User以避免循环导入
async def get_user_from_db(db: AsyncSession, user_id: int):
    from app.models.user import User
    return await db.get(User, user_id)

# OAuth2 token URL
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    scopes={
        "user": "普通用户权限",
        "admin": "管理员权限",
    },
)

def verify_token(token: str) -> Dict[str, Any]:
    """验证JWT令牌
    
    参数:
        token: JWT令牌
        
    返回:
        Dict[str, Any]: 解码后的令牌数据
        
    异常:
        JWTError: 令牌验证失败
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return cast(Dict[str, Any], payload)
    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise

def decode_access_token(token: str) -> Optional[dict]:
    """解码并验证访问令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        # 确保user_id是整数类型
        if "sub" in payload:
            payload["sub"] = int(payload["sub"])
            
        # 验证令牌是否过期
        exp = payload.get("exp")
        if not exp or datetime.fromtimestamp(exp) < datetime.utcnow():
            return None
            
        return payload
    except (JWTError, ValueError):
        return None

def create_access_token(
    subject: int,
    scopes: List[str]
) -> str:
    """创建访问令牌
    
    参数:
        subject: 令牌主体（通常是用户ID）
        scopes: 权限范围列表
        
    返回:
        str: JWT token字符串
    """
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    data = {
        "sub": str(subject),
        "scopes": scopes,
        "exp": expire,
        "type": "access_token"
    }
    try:
        encoded_jwt = jwt.encode(
            data,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="令牌创建失败"
        )

def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建刷新令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh"
    }
    
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create refresh token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="令牌创建失败"
        )

async def verify_token(token: str) -> dict:
    """验证令牌并返回负载
    
    参数:
        token: JWT令牌
        
    返回:
        Optional[dict]: 令牌负载，验证失败返回None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access_token":
            return None
        return payload
    except JWTError:
        return None

async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前用户
    
    用于依赖注入，验证用户身份和权限
    
    参数:
        security_scopes: 安全作用域
        token: JWT token
        
    返回:
        Any: 用户对象
        
    异常:
        HTTPException: 验证失败时抛出
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": authenticate_value},
    )
    
    try:
        payload = verify_token(token)
        token_sub = payload.get("sub")
        if token_sub is None:
            raise credentials_exception
            
        user_id = int(token_sub)
            
        token_type = payload.get("type")
        if token_type != "access_token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌类型",
                headers={"WWW-Authenticate": authenticate_value},
            )
            
        token_scopes = payload.get("scopes", [])
        
        # 验证权限范围
        for scope in security_scopes.scopes:
            if scope not in token_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="权限不足",
                    headers={"WWW-Authenticate": authenticate_value},
                )
                
        user = await db.get(User, user_id)
        if user is None:
            raise credentials_exception
        return user
        
    except JWTError as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise credentials_exception
    except ValidationError as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="认证过程中发生错误"
        )
def get_current_active_user(
    current_user: Any = Depends(get_current_user)
) -> Any:
    """获取当前活跃用户（已认证用户）
    
    参数:
        current_user: 当前认证用户
        
    返回:
        Any: 用户对象
    """
    return current_user

def get_current_admin_user(
    current_user: Any = Security(get_current_user, scopes=["admin"])
) -> Any:
    """获取当前管理员用户（带管理员权限）
    
    参数:
        current_user: 当前认证用户
        
    返回:
        Any: 用户对象
    """
    return current_user

def setup_security_middleware(app: FastAPI) -> None:
    """配置安全相关的中间件
    
    参数:
        app: FastAPI 应用实例
    """
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # 添加安全相关的响应头
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

def requires_scope(required_scope: str):
    """检查用户是否具有特定权限的装饰器    
    用法:
        @router.get("/admin-only")
        @requires_scope("admin")
        async def admin_route():
            return {"message": "仅管理员可见"}    
    参数:
        required_scope: 所需的权限范围
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            auth = request.headers.get("Authorization")
            if not auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="需要认证",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            try:
                token = extract_token_from_header(auth)
                payload = verify_token(token)
                token_scopes = payload.get("scopes", [])
                if required_scope not in token_scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="权限不足"
                    )
                return await func(request, *args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Token verification failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的凭据"
                )
        return wrapper
    return decorator

def extract_token_from_header(authorization: str) -> str:
    """从 Authorization 头部提取 token
    
    参数:
        authorization: Authorization 头部值
        
    返回:
        str: JWT token
        
    异常:
        HTTPException: 格式无效时抛出
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证头部",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ")[1]

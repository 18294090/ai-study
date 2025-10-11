"""
密码哈希和验证功能模块

用于处理密码的哈希和验证，分离自security模块以避免循环导入
"""
from passlib.context import CryptContext

# 配置密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    
    参数:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    返回:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """获取密码哈希
    
    参数:
        password: 明文密码
        
    返回:
        str: 哈希后的密码
    """
    return pwd_context.hash(password)

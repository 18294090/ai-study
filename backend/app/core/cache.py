from fastapi import Request, Response
import aioredis
from functools import wraps
import json
from app.core.config import settings

redis = aioredis.from_url(settings.REDIS_URL)

async def cache_response(
    request: Request,
    response: Response,
    expire: int = 300
):
    """缓存响应数据"""
    if request.method != "GET":
        return response
        
    cache_key = f"cache:{request.url.path}:{request.query_params}"
    
    # 尝试从缓存获取
    cached = await redis.get(cache_key)
    if cached:
        return Response(
            content=cached,
            media_type="application/json"
        )
    
    # 缓存新响应
    await redis.set(
        cache_key,
        response.body,
        expire=expire
    )
    
    return response

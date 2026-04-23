# vibe2crazy/backend/app/routers/config.py
"""公开配置路由（无需认证）"""

from fastapi import APIRouter
from app.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def get_public_config():
    """获取公开配置（用于前端更新检查）"""
    return {
        "current_version": settings.current_version,
        "update_server_url": settings.update_server_url,
    }
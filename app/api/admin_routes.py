"""
管理后台 API 路由
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.admin_auth import admin_required
from app.core.context import AppContext
from app.models import User
from app.services.admin_service import AdminService

logger = logging.getLogger(__name__)


# ==================== Request/Response Models ====================


class UserCreate(BaseModel):
    """创建用户请求"""

    username: str = Field(..., description="用户名")
    email: Optional[str] = Field(None, description="邮箱")
    role: str = Field("admin", description="角色: super_admin 或 admin")
    permissions: Optional[Dict[str, List[str]]] = Field(None, description="权限配置")


class UserUpdate(BaseModel):
    """更新用户请求"""

    email: Optional[str] = Field(None, description="邮箱")
    role: Optional[str] = Field(None, description="角色")
    permissions: Optional[Dict[str, List[str]]] = Field(None, description="权限配置")
    is_active: Optional[bool] = Field(None, description="是否启用")


class UserResponse(BaseModel):
    """用户响应"""

    username: str
    email: Optional[str]
    role: str
    permissions: Optional[Dict[str, List[str]]]
    is_active: bool
    created_at: str
    last_login_at: Optional[str]


class SettingUpdate(BaseModel):
    """配置更新请求"""

    value: Any = Field(..., description="配置值")
    category: str = Field(..., description="分类")
    description: Optional[str] = Field(None, description="说明")


class DashboardStats(BaseModel):
    """Dashboard 统计数据"""

    database_available: bool = True
    reviews: Dict[str, int]
    tokens: Dict[str, int]
    webhooks: Dict[str, Any]
    repositories: Dict[str, int]


# ==================== Router ====================


def create_admin_router(context: AppContext) -> APIRouter:
    """创建管理后台路由"""
    router = APIRouter(prefix="/admin", tags=["Admin"])

    # ==================== Dashboard ====================

    @router.get("/dashboard/stats", response_model=DashboardStats)
    async def get_dashboard_stats(
        request: Request, admin: User = Depends(admin_required())
    ):
        """获取 Dashboard 统计数据"""
        database = getattr(request.state, "database", None)
        if not database:
            logger.warning("数据库未初始化，返回空统计数据")
            return {
                "database_available": False,
                "reviews": {"total": 0, "today": 0, "week": 0, "month": 0},
                "tokens": {"total": 0, "today": 0, "week": 0, "month": 0},
                "webhooks": {"total": 0, "today": 0, "success_rate": 0.0},
                "repositories": {"total": 0, "active": 0},
            }

        async with database.session() as session:
            service = AdminService(session)
            stats = await service.get_dashboard_stats()
            stats["database_available"] = True
            return stats

    # ==================== 管理员用户管理 ====================

    @router.get("/users", response_model=List[UserResponse])
    async def list_users(
        request: Request,
        is_active: Optional[bool] = None,
        admin: User = Depends(admin_required("users", "read")),
    ):
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        async with database.session() as session:
            service = AdminService(session)
            users = await service.list_users(is_active=is_active)
            return [
                UserResponse(
                    username=u.username,
                    email=u.email,
                    role=u.role,
                    permissions=json.loads(u.permissions) if u.permissions else None,
                    is_active=u.is_active,
                    created_at=u.created_at.isoformat(),
                    last_login_at=(
                        u.last_login_at.isoformat() if u.last_login_at else None
                    ),
                )
                for u in users
            ]

    @router.post("/users", response_model=UserResponse)
    async def create_user(
        request: Request,
        payload: UserCreate,
        admin: User = Depends(admin_required("users", "write")),
    ):
        """创建用户"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        if admin.role != "super_admin":
            raise HTTPException(status_code=403, detail="需要超级管理员权限")

        async with database.session() as session:
            service = AdminService(session)

            existing = await service.get_user(payload.username)
            if existing:
                raise HTTPException(status_code=400, detail="用户名已存在")

            user = await service.create_user(
                username=payload.username,
                email=payload.email,
                role=payload.role,
                permissions=payload.permissions,
            )
            await session.commit()

            return UserResponse(
                username=user.username,
                email=user.email,
                role=user.role,
                permissions=json.loads(user.permissions) if user.permissions else None,
                is_active=user.is_active,
                created_at=user.created_at.isoformat(),
                last_login_at=None,
            )

    @router.put("/users/{username}", response_model=UserResponse)
    async def update_user(
        request: Request,
        username: str,
        payload: UserUpdate,
        admin: User = Depends(admin_required("users", "write")),
    ):
        """更新用户"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        if admin.role != "super_admin" and admin.username != username:
            raise HTTPException(status_code=403, detail="只能修改自己的信息")

        async with database.session() as session:
            service = AdminService(session)
            user = await service.update_user(
                username=username,
                email=payload.email,
                role=payload.role,
                permissions=payload.permissions,
                is_active=payload.is_active,
            )
            if not user:
                raise HTTPException(status_code=404, detail="用户不存在")

            await session.commit()

            return UserResponse(
                username=user.username,
                email=user.email,
                role=user.role,
                permissions=json.loads(user.permissions) if user.permissions else None,
                is_active=user.is_active,
                created_at=user.created_at.isoformat(),
                last_login_at=(
                    user.last_login_at.isoformat() if user.last_login_at else None
                ),
            )

    @router.delete("/users/{username}")
    async def delete_user(
        request: Request,
        username: str,
        admin: User = Depends(admin_required("users", "delete")),
    ):
        """删除用户"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        if admin.role != "super_admin":
            raise HTTPException(status_code=403, detail="需要超级管理员权限")

        if admin.username == username:
            raise HTTPException(status_code=400, detail="不能删除自己")

        async with database.session() as session:
            service = AdminService(session)
            deleted = await service.delete_user(username)
            if not deleted:
                raise HTTPException(status_code=404, detail="用户不存在")

            await session.commit()
            return {"success": True, "message": f"已删除用户 {username}"}

    # ==================== 全局配置管理 ====================

    @router.get("/settings")
    async def get_settings(
        request: Request,
        category: Optional[str] = None,
        admin: User = Depends(admin_required("config", "read")),
    ):
        """获取全局配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        async with database.session() as session:
            service = AdminService(session)
            settings = await service.get_all_settings(category=category)

            return [
                {
                    "key": s.key,
                    "value": json.loads(s.value),
                    "category": s.category,
                    "description": s.description,
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in settings
            ]

    @router.put("/settings/{key}")
    async def update_setting(
        request: Request,
        key: str,
        payload: SettingUpdate,
        admin: User = Depends(admin_required("config", "write")),
    ):
        """更新全局配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        async with database.session() as session:
            service = AdminService(session)
            setting = await service.set_setting(
                key=key,
                value=payload.value,
                category=payload.category,
                description=payload.description,
            )
            await session.commit()

            return {
                "key": setting.key,
                "value": json.loads(setting.value),
                "category": setting.category,
                "description": setting.description,
                "updated_at": setting.updated_at.isoformat(),
            }

    @router.delete("/settings/{key}")
    async def delete_setting(
        request: Request,
        key: str,
        admin: User = Depends(admin_required("config", "delete")),
    ):
        """删除全局配置"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        async with database.session() as session:
            service = AdminService(session)
            deleted = await service.delete_setting(key)
            if not deleted:
                raise HTTPException(status_code=404, detail="配置不存在")

            await session.commit()
            return {"success": True, "message": f"已删除配置 {key}"}

    # ==================== Webhook 日志 ====================

    @router.get("/webhooks/logs")
    async def list_webhook_logs(
        request: Request,
        repository_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        admin: User = Depends(admin_required("webhooks", "read")),
    ):
        """获取 Webhook 日志列表"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        async with database.session() as session:
            service = AdminService(session)
            logs = await service.list_webhook_logs(
                repository_id=repository_id,
                status=status,
                limit=limit,
                offset=offset,
            )

            return [
                {
                    "id": log.id,
                    "request_id": log.request_id,
                    "repository_id": log.repository_id,
                    "event_type": log.event_type,
                    "status": log.status,
                    "error_message": log.error_message,
                    "processing_time_ms": log.processing_time_ms,
                    "retry_count": log.retry_count,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]

    @router.get("/webhooks/logs/{log_id}")
    async def get_webhook_log_detail(
        request: Request,
        log_id: int,
        admin: User = Depends(admin_required("webhooks", "read")),
    ):
        """获取 Webhook 日志详情"""
        database = getattr(request.state, "database", None)
        if not database:
            raise HTTPException(status_code=503, detail="数据库未启用")

        async with database.session() as session:
            from app.models import WebhookLog
            from sqlalchemy import select

            stmt = select(WebhookLog).where(WebhookLog.id == log_id)
            result = await session.execute(stmt)
            log = result.scalar_one_or_none()

            if not log:
                raise HTTPException(status_code=404, detail="日志不存在")

            import json

            return {
                "id": log.id,
                "request_id": log.request_id,
                "repository_id": log.repository_id,
                "event_type": log.event_type,
                "payload": json.loads(log.payload),
                "status": log.status,
                "error_message": log.error_message,
                "processing_time_ms": log.processing_time_ms,
                "retry_count": log.retry_count,
                "created_at": log.created_at.isoformat(),
                "updated_at": log.updated_at.isoformat(),
            }

    return router

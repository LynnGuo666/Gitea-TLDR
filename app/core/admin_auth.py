"""
管理员权限验证中间件和工具函数
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser

logger = logging.getLogger(__name__)


async def get_admin_user(session: AsyncSession, username: str) -> Optional[AdminUser]:
    """
    从数据库获取管理员用户

    Args:
        session: 数据库会话
        username: 用户名

    Returns:
        AdminUser 或 None
    """
    stmt = select(AdminUser).where(
        AdminUser.username == username, AdminUser.is_active == True
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_admin_user(
    session: AsyncSession,
    username: str,
    email: Optional[str] = None,
    role: str = "admin",
    permissions: Optional[str] = None,
) -> AdminUser:
    """
    创建管理员用户

    Args:
        session: 数据库会话
        username: 用户名
        email: 邮箱
        role: 角色（super_admin 或 admin）
        permissions: 权限配置（JSON字符串）

    Returns:
        创建的 AdminUser
    """
    admin = AdminUser(
        username=username,
        email=email,
        role=role,
        permissions=permissions,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    logger.info(f"创建管理员用户: {username} ({role})")
    return admin


async def ensure_initial_admin(
    session: AsyncSession, initial_username: Optional[str]
) -> None:
    """
    确保初始管理员存在

    Args:
        session: 数据库会话
        initial_username: 初始管理员用户名
    """
    if not initial_username:
        return

    # 检查是否已有管理员
    stmt = select(AdminUser).limit(1)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        await create_admin_user(session, username=initial_username, role="super_admin")
        await session.commit()
        logger.info(f"初始化超级管理员: {initial_username}")


async def check_admin_permission(
    request: Request,
    required_resource: Optional[str] = None,
    required_action: Optional[str] = None,
) -> AdminUser:
    """
    检查管理员权限

    Args:
        request: FastAPI Request 对象
        required_resource: 需要的资源权限（如 "repos", "config"）
        required_action: 需要的操作权限（如 "read", "write"）

    Returns:
        AdminUser

    Raises:
        HTTPException: 如果未登录或无权限
    """
    # 从请求上下文获取当前用户
    # 这里需要与 OAuth 登录集成
    auth_status = getattr(request.state, "auth_status", None)
    if not auth_status or not auth_status.get("loggedIn"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录")

    username = auth_status.get("user", {}).get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取用户信息"
        )

    # 从数据库获取管理员信息
    database = getattr(request.app.state, "database", None)
    if not database:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库服务不可用"
        )

    async with database.session() as session:
        admin = await get_admin_user(session, username)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
            )

        # 检查特定权限
        if required_resource and required_action:
            if not admin.has_permission(required_resource, required_action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少 {required_resource}.{required_action} 权限",
                )

        return admin


def admin_required(resource: Optional[str] = None, action: Optional[str] = None):
    """
    管理员权限装饰器

    Args:
        resource: 资源名称
        action: 操作类型

    Usage:
        @router.get("/admin/something")
        async def get_something(
            request: Request,
            admin: AdminUser = Depends(admin_required("repos", "read"))
        ):
            ...
    """

    async def dependency(request: Request) -> AdminUser:
        return await check_admin_permission(request, resource, action)

    return dependency

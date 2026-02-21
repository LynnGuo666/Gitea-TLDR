from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

logger = logging.getLogger(__name__)


async def get_admin_user(session: AsyncSession, username: str) -> Optional[User]:
    stmt = select(User).where(
        User.username == username,
        User.role.in_(["admin", "super_admin"]),
        User.is_active == True,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    email: Optional[str] = None,
    role: str = "user",
    permissions: Optional[str] = None,
) -> User:
    user = User(
        username=username,
        email=email,
        role=role,
        permissions=permissions,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    logger.info(f"创建用户: {username} ({role})")
    return user


async def ensure_initial_admin(
    session: AsyncSession, initial_username: Optional[str]
) -> None:
    if not initial_username:
        return

    stmt = select(User).where(
        User.role == "super_admin",
        User.is_active.is_(True),
    ).limit(1)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        initial_user_stmt = select(User).where(User.username == initial_username).limit(1)
        initial_user_result = await session.execute(initial_user_stmt)
        initial_user = initial_user_result.scalar_one_or_none()

        if initial_user:
            initial_user.role = "super_admin"
            initial_user.is_active = True
            logger.info(f"提升初始用户为超级管理员: {initial_username}")
        else:
            await create_user(session, username=initial_username, role="super_admin")
        await session.commit()
        logger.info(f"初始化超级管理员: {initial_username}")


async def check_admin_permission(
    request: Request,
    required_resource: Optional[str] = None,
    required_action: Optional[str] = None,
) -> User:
    auth_status = getattr(request.state, "auth_status", None)
    if not auth_status or not auth_status.get("loggedIn"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录")

    username = auth_status.get("user", {}).get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取用户信息"
        )

    database = getattr(request.state, "database", None)
    if not database:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="服务暂时不可用"
        )

    async with database.session() as session:
        admin = await get_admin_user(session, username)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限"
            )

        if required_resource and required_action:
            if not admin.has_permission(required_resource, required_action):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"缺少 {required_resource}.{required_action} 权限",
                )

        return admin


def admin_required(resource: Optional[str] = None, action: Optional[str] = None):
    async def dependency(request: Request) -> User:
        return await check_admin_permission(request, resource, action)

    return dependency

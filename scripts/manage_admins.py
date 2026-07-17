#!/usr/bin/env python3
"""
手动添加管理员用户的脚本
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import Database
from app.core.admin_auth import create_user


async def add_admin(
    username: str, email: Optional[str] = None, role: str = "super_admin"
):
    """添加管理员用户"""
    database = Database(settings.effective_database_url)
    await database.init()

    async with database.session() as session:
        # 检查用户是否已存在
        from app.models import Actor
        from sqlalchemy import select

        stmt = select(Actor).where(Actor.external_username == username)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✅ 用户 {username} 已经是管理员")
            print(f"   角色: {existing.role}")
            print(f"   状态: {'激活' if existing.is_active else '未激活'}")
            print(f"   创建时间: {existing.created_at}")
            return

        # 创建新管理员
        await create_user(
            session=session, username=username, email=email, role=role
        )
        await session.commit()

        print(f"✅ 成功添加管理员: {username}")
        print(f"   角色: {role}")
        print(f"   邮箱: {email or '未设置'}")
        print(f"\n现在你可以使用该用户名登录并访问管理后台了！")

    await database.close()


async def list_admins():
    """列出所有管理员"""
    database = Database(settings.effective_database_url)
    await database.init()

    async with database.session() as session:
        from app.models import Actor
        from sqlalchemy import select

        stmt = select(Actor).order_by(Actor.created_at.desc())
        result = await session.execute(stmt)
        admins = result.scalars().all()

        if not admins:
            print("❌ 当前没有管理员用户")
            return

        print(f"\n📋 当前管理员列表 ({len(admins)} 人):\n")
        for admin in admins:
            status = "✅ 激活" if admin.is_active else "❌ 未激活"
            print(f"  - {admin.external_username}")
            print(f"    角色: {admin.role}")
            print(f"    状态: {status}")
            print(f"    创建时间: {admin.created_at}")
            print()

    await database.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="管理后台管理员管理工具")
    parser.add_argument(
        "action", choices=["add", "list"], help="操作: add(添加) 或 list(列出)"
    )
    parser.add_argument("--username", help="用户名（Gitea 用户名）")
    parser.add_argument("--email", help="邮箱（可选）")
    parser.add_argument(
        "--role", choices=["super_admin", "admin"], default="super_admin", help="角色"
    )

    args = parser.parse_args()

    if args.action == "list":
        asyncio.run(list_admins())
    elif args.action == "add":
        if not args.username:
            print("❌ 错误: 必须指定 --username")
            sys.exit(1)
        asyncio.run(add_admin(args.username, args.email, args.role))

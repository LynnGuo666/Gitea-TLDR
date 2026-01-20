"""
管理后台服务
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminSettings,
    AdminUser,
    ApiKey,
    Repository,
    ReviewSession,
    UsageStat,
    WebhookLog,
)

logger = logging.getLogger(__name__)


class AdminService:
    """管理后台服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== AdminUser 操作 ====================

    async def list_admin_users(
        self, is_active: Optional[bool] = None
    ) -> List[AdminUser]:
        """获取管理员列表"""
        stmt = select(AdminUser)
        if is_active is not None:
            stmt = stmt.where(AdminUser.is_active == is_active)
        stmt = stmt.order_by(AdminUser.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_admin_user(self, username: str) -> Optional[AdminUser]:
        """获取管理员用户"""
        stmt = select(AdminUser).where(AdminUser.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_admin_user(
        self,
        username: str,
        email: Optional[str] = None,
        role: str = "admin",
        permissions: Optional[Dict[str, List[str]]] = None,
    ) -> AdminUser:
        """创建管理员用户"""
        admin = AdminUser(
            username=username,
            email=email,
            role=role,
            permissions=json.dumps(permissions) if permissions else None,
            is_active=True,
        )
        self.session.add(admin)
        await self.session.flush()
        return admin

    async def update_admin_user(
        self,
        username: str,
        email: Optional[str] = None,
        role: Optional[str] = None,
        permissions: Optional[Dict[str, List[str]]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[AdminUser]:
        """更新管理员用户"""
        admin = await self.get_admin_user(username)
        if not admin:
            return None

        if email is not None:
            admin.email = email
        if role is not None:
            admin.role = role
        if permissions is not None:
            admin.permissions = json.dumps(permissions)
        if is_active is not None:
            admin.is_active = is_active

        await self.session.flush()
        return admin

    async def delete_admin_user(self, username: str) -> bool:
        """删除管理员用户"""
        stmt = delete(AdminUser).where(AdminUser.username == username)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    # ==================== AdminSettings 操作 ====================

    async def get_all_settings(
        self, category: Optional[str] = None
    ) -> List[AdminSettings]:
        """获取所有配置"""
        stmt = select(AdminSettings)
        if category:
            stmt = stmt.where(AdminSettings.category == category)
        stmt = stmt.order_by(AdminSettings.category, AdminSettings.key)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_setting(self, key: str) -> Optional[AdminSettings]:
        """获取单个配置"""
        stmt = select(AdminSettings).where(AdminSettings.key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_setting(
        self, key: str, value: Any, category: str, description: Optional[str] = None
    ) -> AdminSettings:
        """设置配置"""
        setting = await self.get_setting(key)
        if setting:
            setting.value = json.dumps(value)
            if description:
                setting.description = description
        else:
            setting = AdminSettings(
                key=key,
                value=json.dumps(value),
                category=category,
                description=description,
            )
            self.session.add(setting)
        await self.session.flush()
        return setting

    async def delete_setting(self, key: str) -> bool:
        """删除配置"""
        stmt = delete(AdminSettings).where(AdminSettings.key == key)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    # ==================== Dashboard 统计 ====================

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """获取 Dashboard 统计数据"""
        # 今日、本周、本月的日期范围
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # 审查次数统计
        total_reviews = await self._count_reviews()
        today_reviews = await self._count_reviews(start_date=today)
        week_reviews = await self._count_reviews(start_date=week_ago)
        month_reviews = await self._count_reviews(start_date=month_ago)

        # Token 消耗统计
        total_tokens = await self._sum_tokens()
        today_tokens = await self._sum_tokens(start_date=today)
        week_tokens = await self._sum_tokens(start_date=week_ago)
        month_tokens = await self._sum_tokens(start_date=month_ago)

        # Webhook 统计
        total_webhooks = await self._count_webhooks()
        today_webhooks = await self._count_webhooks(start_date=today)
        webhook_success_rate = await self._webhook_success_rate()

        # 仓库统计
        total_repos = await self._count_repositories()
        active_repos = await self._count_repositories(is_active=True)

        return {
            "reviews": {
                "total": total_reviews,
                "today": today_reviews,
                "week": week_reviews,
                "month": month_reviews,
            },
            "tokens": {
                "total": total_tokens,
                "today": today_tokens,
                "week": week_tokens,
                "month": month_tokens,
            },
            "webhooks": {
                "total": total_webhooks,
                "today": today_webhooks,
                "success_rate": webhook_success_rate,
            },
            "repositories": {
                "total": total_repos,
                "active": active_repos,
            },
        }

    async def _count_reviews(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> int:
        """统计审查次数"""
        stmt = select(func.count(ReviewSession.id))
        if start_date:
            stmt = stmt.where(ReviewSession.started_at >= start_date)
        if end_date:
            stmt = stmt.where(ReviewSession.started_at <= end_date)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _sum_tokens(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> int:
        """统计 Token 消耗"""
        stmt = select(
            func.sum(UsageStat.estimated_input_tokens)
            + func.sum(UsageStat.estimated_output_tokens)
        )
        if start_date:
            stmt = stmt.where(UsageStat.created_at >= start_date)
        if end_date:
            stmt = stmt.where(UsageStat.created_at <= end_date)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _count_webhooks(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> int:
        """统计 Webhook 次数"""
        stmt = select(func.count(WebhookLog.id))
        if start_date:
            stmt = stmt.where(WebhookLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(WebhookLog.created_at <= end_date)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def _webhook_success_rate(self) -> float:
        """计算 Webhook 成功率"""
        total_stmt = select(func.count(WebhookLog.id))
        total_result = await self.session.execute(total_stmt)
        total = total_result.scalar() or 0

        if total == 0:
            return 100.0

        success_stmt = select(func.count(WebhookLog.id)).where(
            WebhookLog.status == "success"
        )
        success_result = await self.session.execute(success_stmt)
        success = success_result.scalar() or 0

        return (success / total) * 100

    async def _count_repositories(self, is_active: Optional[bool] = None) -> int:
        """统计仓库数量"""
        stmt = select(func.count(Repository.id))
        if is_active is not None:
            stmt = stmt.where(Repository.is_active == is_active)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ==================== Webhook 日志操作 ====================

    async def create_webhook_log(
        self,
        request_id: str,
        repository_id: int,
        event_type: str,
        payload: str,
        status: str = "success",
        error_message: Optional[str] = None,
        processing_time_ms: int = 0,
    ) -> WebhookLog:
        """创建 Webhook 日志"""
        log = WebhookLog(
            request_id=request_id,
            repository_id=repository_id,
            event_type=event_type,
            payload=payload,
            status=status,
            error_message=error_message,
            processing_time_ms=processing_time_ms,
            retry_count=0,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_webhook_logs(
        self,
        repository_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[WebhookLog]:
        """获取 Webhook 日志列表"""
        stmt = select(WebhookLog)
        if repository_id:
            stmt = stmt.where(WebhookLog.repository_id == repository_id)
        if status:
            stmt = stmt.where(WebhookLog.status == status)
        stmt = stmt.order_by(WebhookLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_old_webhook_logs(
        self, retention_days: int, retention_days_failed: int
    ) -> int:
        """清理旧的 Webhook 日志"""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_date_failed = datetime.now() - timedelta(days=retention_days_failed)

        # 删除成功的旧日志
        success_stmt = delete(WebhookLog).where(
            and_(WebhookLog.status == "success", WebhookLog.created_at < cutoff_date)
        )
        success_result = await self.session.execute(success_stmt)

        # 删除失败的旧日志
        failed_stmt = delete(WebhookLog).where(
            and_(
                WebhookLog.status == "error",
                WebhookLog.created_at < cutoff_date_failed,
            )
        )
        failed_result = await self.session.execute(failed_stmt)

        total_deleted = success_result.rowcount + failed_result.rowcount
        if total_deleted > 0:
            logger.info(f"清理了 {total_deleted} 条旧 Webhook 日志")
        return total_deleted

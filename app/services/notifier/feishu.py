"""飞书群机器人通知服务。

读取 app_settings 中的飞书配置，把审查摘要 + 严重级别 + 链接
推送到飞书自定义机器人 webhook。失败只 log.warning，绝不抛出
（通知是非致命旁路，不应影响主审查流程）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Optional, Tuple

import httpx

from app.services.db_service import DBService

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10.0


class FeishuNotifier:
    """飞书群机器人推送器。"""

    def __init__(self, db_service: DBService):
        self._db = db_service

    async def _config(self) -> Tuple[bool, str, str, str]:
        """从 app_settings 读取飞书配置。

        Returns:
            (enabled, webhook_url, secret, mode) 元组；缺失项以默认值兜底。
        """
        enabled = bool(await self._db.get_app_setting("feishu_enabled", False))
        webhook_url = str(
            await self._db.get_app_setting("feishu_webhook_url", "") or ""
        )
        secret = str(await self._db.get_app_setting("feishu_secret", "") or "")
        mode = str(await self._db.get_app_setting("feishu_mode", "all") or "all")
        return enabled, webhook_url, secret, mode

    async def send(
        self,
        *,
        title: str,
        summary: str,
        severity: Optional[str],
        link: Optional[str],
        is_failure: bool,
    ) -> bool:
        """推送一条审查结果卡片到飞书群。

        Args:
            title: 卡片标题（如 owner/repo#pr_number 或 from_tag...to_tag）
            summary: 摘要 markdown 文本
            severity: 严重级别（critical/high/medium/low/none 之一，可空）
            link: 结果详情链接（Gitea PR/Issue/compare 页，可空）
            is_failure: 本次审查是否判定为失败（驱动 failure_only 过滤）

        Returns:
            是否成功送达。失败时仅 log.warning，不抛异常。
        """
        try:
            enabled, webhook_url, secret, mode = await self._config()
            if not enabled or not webhook_url:
                return False
            # mode=failure_only 时仅推送失败用例
            if mode == "failure_only" and not is_failure:
                return False

            payload = self._build_payload(
                title=title,
                summary=summary,
                severity=severity,
                link=link,
                is_failure=is_failure,
            )
            headers = {"Content-Type": "application/json"}
            if secret:
                payload = self._sign(payload, secret)

            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    webhook_url, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
            # 飞书成功响应 {code: 0, msg: "success"} 或 {StatusCode: 0}
            code = data.get("code", data.get("StatusCode", 0))
            if code not in (0, None):
                logger.warning("飞书推送返回非 0 状态: %s", data)
                return False
            logger.info("飞书推送成功: %s", title)
            return True
        except Exception as exc:
            logger.warning("飞书推送失败（非致命）: %s", exc)
            return False

    @staticmethod
    def _build_payload(
        *,
        title: str,
        summary: str,
        severity: Optional[str],
        link: Optional[str],
        is_failure: bool,
    ) -> dict:
        """构造 interactive 卡片 payload。"""
        severity_text = (severity or "unknown").upper()
        status_text = "❌ 存在风险" if is_failure else "✅ 通过"
        # 截断过长的摘要，避免飞书卡片超限
        trimmed = (summary or "").strip()
        if len(trimmed) > 1800:
            trimmed = trimmed[:1800] + "\n\n…（摘要已截断）"

        elements: list[dict] = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": trimmed or "未生成摘要",
                },
            },
            {
                "tag": "div",
                "fields": [
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**严重级别**\n{severity_text}",
                        },
                    },
                    {
                        "is_short": True,
                        "text": {
                            "tag": "lark_md",
                            "content": f"**结果**\n{status_text}",
                        },
                    },
                ],
            },
        ]
        if link:
            elements.append(
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看详情"},
                            "url": link,
                            "type": "primary",
                        }
                    ],
                }
            )

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"代码审查 · {title}"},
                    "template": "red" if is_failure else "green",
                },
                "elements": elements,
            },
        }

    @staticmethod
    def _sign(payload: dict, secret: str) -> dict:
        """对飞书自定义机器人加签（timestamp + HMAC-SHA256 secret）。"""
        import time

        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        payload["timestamp"] = timestamp
        payload["sign"] = sign
        return payload

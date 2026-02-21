"""OAuth登录与用户会话管理"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request, Response

from app.core import settings
from .gitea_client import GiteaClient

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """前端登录用户的访问令牌信息"""

    access_token: str
    refresh_token: Optional[str]
    scope: str
    expires_at: float
    user: Dict[str, Any]
    user_id: Optional[int] = field(default=None)  # DB User.id


class AuthManager:
    """封装OAuth流程和会话生命周期"""

    def __init__(self) -> None:
        self.enabled = bool(settings.oauth_client_id and settings.oauth_redirect_url)
        self._state_store: Dict[str, float] = {}
        self._sessions: Dict[str, SessionData] = {}
        self._lock = Lock()
        self._authorize_endpoint = (
            f"{settings.gitea_url.rstrip('/')}/login/oauth/authorize"
        )
        self._token_endpoint = (
            f"{settings.gitea_url.rstrip('/')}/login/oauth/access_token"
        )
        self._userinfo_endpoint = f"{settings.gitea_url.rstrip('/')}/api/v1/user"

    def _generate_state(self) -> str:
        state = secrets.token_urlsafe(32)
        with self._lock:
            self._state_store[state] = time.time() + 600  # 10分钟有效期
        return state

    def _consume_state(self, state: str) -> bool:
        with self._lock:
            expires = self._state_store.pop(state, None)
        return bool(expires and expires > time.time())

    def build_authorize_url(self) -> str:
        if not self.enabled:
            raise HTTPException(status_code=400, detail="OAuth 尚未配置")
        state = self._generate_state()
        params = {
            "client_id": settings.oauth_client_id,
            "redirect_uri": settings.oauth_redirect_url,
            "response_type": "code",
            "state": state,
        }
        if settings.oauth_scopes:
            params["scope"] = " ".join(settings.oauth_scopes)
        return f"{self._authorize_endpoint}?{urlencode(params)}"

    async def _exchange_code(self, code: str) -> Dict[str, Any]:
        payload = {
            "client_id": settings.oauth_client_id,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.oauth_redirect_url,
        }
        if settings.oauth_client_secret:
            payload["client_secret"] = settings.oauth_client_secret

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._token_endpoint,
                headers={"Accept": "application/json"},
                data=payload,
            )
            response.raise_for_status()
            return response.json()

    async def _fetch_user(self, token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                self._userinfo_endpoint,
                headers={"Authorization": f"token {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def handle_callback(
        self,
        code: str,
        state: str,
        response: Response,
        database: Optional[Any] = None,
    ) -> Response:
        if not self.enabled:
            raise HTTPException(status_code=400, detail="OAuth 尚未配置")
        if not state or not self._consume_state(state):
            raise HTTPException(status_code=400, detail="state 校验失败")

        token_payload = await self._exchange_code(code)
        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="获取access_token失败")

        user_info = await self._fetch_user(access_token)
        username = user_info.get("login") or user_info.get("username")

        expires_in = token_payload.get("expires_in", 3600)
        session = SessionData(
            access_token=access_token,
            refresh_token=token_payload.get("refresh_token"),
            scope=token_payload.get("scope", ""),
            expires_at=time.time() + int(expires_in),
            user={
                "username": username,
                "full_name": user_info.get("full_name"),
                "avatar_url": user_info.get("avatar_url"),
            },
        )

        if database and username:
            try:
                from datetime import datetime, timezone
                from sqlalchemy import select
                from app.models import User

                async with database.session() as db_session:
                    stmt = select(User).where(User.username == username)
                    result = await db_session.execute(stmt)
                    db_user = result.scalar_one_or_none()

                    if db_user is None:
                        db_user = User(
                            username=username,
                            email=user_info.get("email"),
                            role="user",
                            is_active=True,
                        )
                        db_session.add(db_user)

                    db_user.last_login_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    )
                    await db_session.flush()
                    session.user_id = db_user.id
                    await db_session.commit()
            except Exception as exc:
                logger.warning("用户落库失败，跳过: %s", exc)

        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[session_id] = session

        self._attach_cookie(response, session_id, expires_in)
        return response

    def _attach_cookie(
        self, response: Response, session_id: str, expires_in: int
    ) -> None:
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_id,
            max_age=expires_in,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )

    def require_session(self, request: Request) -> SessionData:
        session = self.get_session(request)
        if not session:
            raise HTTPException(status_code=401, detail="请先登录")
        return session

    def get_session(self, request: Request) -> Optional[SessionData]:
        if not self.enabled:
            return None
        session_id = request.cookies.get(settings.session_cookie_name)
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            return None
        if session.expires_at <= time.time():
            self.delete_session(session_id)
            return None
        return session

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def logout(self, request: Request, response: Response) -> None:
        session_id = request.cookies.get(settings.session_cookie_name)
        if session_id:
            self.delete_session(session_id)
        response.delete_cookie(
            key=settings.session_cookie_name,
            path="/",
        )

    def get_status_payload(self, request: Request) -> Dict[str, Any]:
        session = self.get_session(request)
        return {
            "enabled": self.enabled,
            "logged_in": bool(session),
            "user": session.user if session else None,
        }

    def build_user_client(self, session: SessionData) -> GiteaClient:
        return GiteaClient(settings.gitea_url, session.access_token, settings.debug)

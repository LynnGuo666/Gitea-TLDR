"""真实 OAuth 集成测试。

默认不运行，需手动执行：
    pytest tests/test_oauth_live.py -v -s

流程：
1. 打印授权 URL
2. 等待用户粘贴 callback URL
3. 解析 code/state，调用 handle_callback
4. 用真实 token 验证 /api/v1/user
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.mark.live
def test_oauth_full_flow() -> None:
    from app.core import settings
    from app.gitea.auth import AuthManager
    from fastapi import Response

    if not settings.oauth_client_id or not settings.oauth_redirect_url:
        pytest.skip("未配置 OAuth 凭据（OAUTH_CLIENT_ID / OAUTH_REDIRECT_URL）")

    auth_manager = AuthManager()
    assert auth_manager.enabled, "AuthManager 未启用，检查 .env 配置"

    authorize_url = auth_manager.build_authorize_url()
    print(
        f"\n请在浏览器中打开以下 OAuth 授权链接：\n  {authorize_url}\n\n"
        f"授权后，Gitea 会重定向到 {settings.oauth_redirect_url}\n"
        "（若 localhost 服务未启动，浏览器报错是正常的，直接从地址栏复制完整 URL）\n"
    )

    callback_url = input("Callback URL: ").strip()
    assert callback_url, "未输入 callback URL"

    parsed = urlparse(callback_url)
    params = parse_qs(parsed.query)
    code_list = params.get("code", [])
    state_list = params.get("state", [])
    assert code_list, "callback URL 中缺少 code 参数"
    assert state_list, "callback URL 中缺少 state 参数"

    code = code_list[0]
    state = state_list[0]

    response = Response()
    asyncio.run(auth_manager.handle_callback(code, state, response, database=None))

    assert auth_manager._sessions, "handle_callback 后 _sessions 为空"
    session = list(auth_manager._sessions.values())[0]

    assert session.access_token, "access_token 为空"
    assert session.user.get("username"), "session.user 缺少 username"

    login = session.user["username"]
    print(f"\n✓ OAuth 流程成功，用户：{login}")

    # 用真实 token 验证 Gitea API
    import httpx

    resp = httpx.get(
        f"{settings.gitea_url.rstrip('/')}/api/v1/user",
        headers={"Authorization": f"token {session.access_token}"},
        timeout=15,
    )
    assert resp.status_code == 200, f"GET /api/v1/user 返回 {resp.status_code}"
    user_data = resp.json()
    assert user_data.get("login") == login, (
        f"API 返回 login={user_data.get('login')} 与 session login={login} 不一致"
    )
    print(f"✓ Gitea API 验证成功：/api/v1/user 返回 login={login}")

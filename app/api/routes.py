"""API routes.

应用内部直接使用当前领域模型；HTTP 对外路径由 main.py 挂到 /api/v2。
"""

from __future__ import annotations

import json
import secrets
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel

from app.core import (
    __release_date__,
    __version__,
    get_all_changelogs_json,
    get_changelog,
    settings,
)
from app.core.context import AppContext
from app.models import Actor
from app.services.audit_service import AuditService
from app.services.db_service import DBService


class ProviderCredentialPayload(BaseModel):
    name: str
    provider: str = "anthropic"
    api_url: Optional[str] = None
    api_key: Optional[str] = None


class ProviderCredentialUpdatePayload(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    is_active: Optional[bool] = None


class ProviderCredentialRotatePayload(BaseModel):
    api_key: str



class RepositoryConfigUpdatePayload(BaseModel):
    engine: Optional[str] = None
    model: Optional[str] = None
    credential_id: Optional[int] = None
    api_url_override: Optional[str] = None
    wire_api: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    custom_prompt: Optional[str] = None
    focus: Optional[list[str]] = None
    features: Optional[list[str]] = None
    is_active: Optional[bool] = None


class AppSettingPayload(BaseModel):
    value: Any
    category: str = "general"
    description: Optional[str] = None


class ActorUpdatePayload(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


def _loads_list(value: Optional[str]) -> list[Any]:
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _serialize_credential(cred) -> dict[str, Any]:
    return {
        "id": cred.id,
        "scope_type": cred.scope_type,
        "scope_key": cred.scope_key,
        "name": cred.name,
        "provider": cred.provider,
        "api_url": cred.api_url,
        "has_api_key": bool(cred.api_key_enc),
        "is_active": cred.is_active,
        "last_used_at": cred.last_used_at.isoformat() if cred.last_used_at else None,
    }


def _serialize_actor(actor) -> dict[str, Any]:
    return {
        "id": actor.id,
        "external_provider": actor.external_provider,
        "external_username": actor.external_username,
        "display_name": actor.display_name,
        "email": actor.email,
        "role": actor.role,
        "permissions": _loads_list(actor.permissions_json),
        "is_active": actor.is_active,
        "last_login_at": actor.last_login_at.isoformat() if actor.last_login_at else None,
        "created_at": actor.created_at.isoformat() if actor.created_at else None,
        "updated_at": actor.updated_at.isoformat() if actor.updated_at else None,
    }


def _serialize_app_setting(setting) -> dict[str, Any]:
    try:
        value = json.loads(setting.value_json)
    except Exception:
        value = setting.value_json
    return {
        "id": setting.id,
        "key": setting.key,
        "category": setting.category,
        "value": value,
        "description": setting.description,
        "updated_by_actor_id": setting.updated_by_actor_id,
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
    }



def _serialize_repo_config(config) -> dict[str, Any]:
    return {
        "id": config.id,
        "repository_id": config.repository_id,
        "scenario": config.scenario,
        "engine": config.engine,
        "model": config.model,
        "credential_id": config.credential_id,
        "credential_name": config.credential.name if config.credential else None,
        "api_url": config.api_url,
        "has_api_key": bool(config.api_key),
        "wire_api": config.wire_api,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "custom_prompt": config.custom_prompt,
        "focus": config.get_focus(),
        "features": config.get_features(),
        "is_active": config.is_active,
    }


def _serialize_run(run) -> dict[str, Any]:
    payload = run.get_analysis_payload()
    related_issues = payload.get("related_issues") if isinstance(payload, dict) else []
    solution_suggestions = payload.get("solution_suggestions") if isinstance(payload, dict) else []
    return {
        "id": run.id,
        "kind": run.kind,
        "repository_id": run.repository_id,
        "repo_full_name": run.repository.full_name if getattr(run, "repository", None) else None,
        "external_number": run.external_number,
        "pr_number": run.external_number if run.kind == "review" else None,
        "issue_number": run.external_number if run.kind == "issue" else None,
        "external_title": run.external_title,
        "pr_title": run.external_title if run.kind == "review" else None,
        "issue_title": run.external_title if run.kind == "issue" else None,
        "external_author": run.external_author,
        "pr_author": run.external_author if run.kind == "review" else None,
        "issue_author": run.external_author if run.kind == "issue" else None,
        "issue_state": run.external_state,
        "trigger_type": run.trigger_type,
        "status": run.status,
        "effective_engine": run.effective_engine,
        "effective_model": run.effective_model,
        "engine": run.effective_engine,
        "model": run.effective_model,
        "config_source": run.config_source,
        "overall_success": run.overall_success,
        "overall_severity": run.overall_severity,
        "summary_markdown": run.summary_markdown,
        "result_payload": payload,
        "analysis_payload": payload,
        "related_issues": related_issues if isinstance(related_issues, list) else [],
        "solution_suggestions": solution_suggestions if isinstance(solution_suggestions, list) else [],
        "related_issue_count": len(related_issues) if isinstance(related_issues, list) else 0,
        "solution_count": len(solution_suggestions) if isinstance(solution_suggestions, list) else 0,
        "related_files": payload.get("related_files", []) if isinstance(payload, dict) else [],
        "next_actions": payload.get("next_actions", []) if isinstance(payload, dict) else [],
        "fallback_mode": payload.get("fallback_mode", "tool") if isinstance(payload, dict) else "tool",
        "focus_areas": payload.get("focus_areas", []) if isinstance(payload, dict) else [],
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": run.duration_seconds,
        "estimated_input_tokens": 0,
        "estimated_output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "total_tokens": 0,
    }


def _serialize_repo(repo: dict[str, Any]) -> dict[str, Any]:
    raw_owner = repo.get("owner")
    owner: dict[str, Any] = raw_owner if isinstance(raw_owner, dict) else {}
    return {
        "id": repo.get("id"),
        "name": repo.get("name"),
        "owner": owner,
        "full_name": repo.get("full_name")
        or f"{owner.get('login') or owner.get('username', '')}/{repo.get('name', '')}",
        "private": repo.get("private"),
        "permissions": repo.get("permissions") or {},
    }


def _serialize_provider_run(run) -> dict[str, Any]:
    return {
        "id": run.id,
        "analysis_run_id": run.analysis_run_id,
        "repository_id": run.repository_id,
        "provider": run.provider,
        "provider_session_id": run.provider_session_id,
        "session_id": run.provider_session_id,
        "scenario": run.scenario,
        "status": run.status,
        "model": run.model,
        "turns": run.turns,
        "tool_calls_count": run.tool_calls_count,
        "messages": json.loads(run.messages_json) if run.messages_json else [],
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cache_creation_input_tokens": run.cache_creation_input_tokens,
        "cache_read_input_tokens": run.cache_read_input_tokens,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_seconds": run.duration_seconds,
        "error_message": run.error_message,
        "error": run.error_message,
        "repo_full_name": run.repository.full_name if getattr(run, "repository", None) else None,
    }


def _serialize_annotation(annotation) -> dict[str, Any]:
    return {
        "id": annotation.id,
        "analysis_run_id": annotation.analysis_run_id,
        "annotation_type": annotation.annotation_type,
        "file_path": annotation.file_path,
        "new_line": annotation.new_line,
        "old_line": annotation.old_line,
        "severity": annotation.severity,
        "body": annotation.body,
        "suggestion": annotation.suggestion,
        "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
    }


def _serialize_webhook_event(event) -> dict[str, Any]:
    return {
        "id": event.id,
        "request_id": event.request_id,
        "repository_id": event.repository_id,
        "analysis_run_id": event.analysis_run_id,
        "event_type": event.event_type,
        "payload": json.loads(event.payload_json) if event.payload_json else None,
        "status": event.status,
        "error_message": event.error_message,
        "processing_time_ms": event.processing_time_ms,
        "retry_count": event.retry_count,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


async def _require_repo_admin_client(context: AppContext, owner: str, repo: str, request: Request):
    session = await context.auth_manager.get_session_async(
        request, getattr(request.state, "database", None)
    )
    if not session:
        raise HTTPException(status_code=401, detail="未登录")

    user_client = context.auth_manager.build_user_client(session)
    perms = await user_client.check_repo_permissions(owner, repo)
    if perms is None:
        raise HTTPException(status_code=502, detail="无法从 Gitea 获取仓库权限")
    if not perms.get("admin"):
        raise HTTPException(status_code=403, detail="需要仓库管理员权限")
    return user_client


def _resolve_webhook_url(request: Request, raw_url: Any) -> str:
    if raw_url is None or raw_url == "":
        return str(request.url_for("webhook"))
    if not isinstance(raw_url, str):
        raise HTTPException(status_code=400, detail="Webhook URL 必须是字符串")
    hook_url = raw_url.strip()
    if not hook_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Webhook URL 必须是完整的 http(s) 地址")
    return hook_url


def _resolve_webhook_events(raw_events: Any) -> list[str]:
    default_events = ["pull_request", "issues", "issue_comment"]
    allowed_events = set(default_events)
    if raw_events is None:
        return default_events
    if not isinstance(raw_events, list):
        raise HTTPException(status_code=400, detail="Webhook events 必须是数组")

    events: list[str] = []
    invalid_events: list[str] = []
    for event in raw_events:
        if not isinstance(event, str):
            invalid_events.append(str(event))
            continue
        normalized = event.strip()
        if normalized not in allowed_events:
            invalid_events.append(normalized)
            continue
        if normalized not in events:
            events.append(normalized)

    if invalid_events:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的 Webhook events: {', '.join(invalid_events)}",
        )
    if not events:
        raise HTTPException(status_code=400, detail="至少选择一个 Webhook event")
    return events


def create_api_router(context: AppContext) -> tuple[APIRouter, APIRouter, APIRouter]:
    router = APIRouter()
    public_router = APIRouter()

    @public_router.get("/health")
    async def health():
        return {"status": "healthy", "version": __version__, "api": "v2"}

    @public_router.get("/version")
    async def public_version():
        return {"version": __version__, "release_date": __release_date__}

    @public_router.get("/changelog")
    async def changelog():
        return get_changelog()

    @public_router.get("/changelog/json")
    async def changelog_json():
        return get_all_changelogs_json()

    @router.get("/config/public")
    async def public_config():
        return {
            "gitea_url": settings.gitea_url,
            "bot_username": settings.bot_username,
            "debug": settings.debug,
            "oauth_enabled": bool(settings.oauth_client_id and settings.oauth_redirect_url),
        }

    @router.get("/version")
    async def version():
        return {"version": __version__, "release_date": __release_date__}

    @router.get("/changelog/json")
    async def api_changelog_json():
        return get_all_changelogs_json()

    @router.get("/providers")
    async def providers():
        items = [
            {"name": name, "label": name.replace("_", " ").title()}
            for name in context.review_engine.registry.list_providers()
        ]
        return {"providers": items, "default": context.review_engine.default_provider_name}

    @router.get("/auth/status")
    async def auth_status(request: Request):
        session = await context.auth_manager.get_session_async(
            request, getattr(request.state, "database", None)
        )
        return {"enabled": context.auth_manager.enabled, "loggedIn": bool(session), "user": session.user if session else None}

    @router.get("/auth/admin-status")
    async def admin_status(request: Request):
        session = await context.auth_manager.get_session_async(
            request, getattr(request.state, "database", None)
        )
        role = None
        is_admin = False
        if session and getattr(request.state, "database", None):
            async with request.state.database.session() as db_session:
                service = DBService(db_session)
                actor = await service.get_or_create_user_by_username(session.user.get("username", ""))
                role = actor.role
                is_admin = actor.role in {"admin", "super_admin"}
        return {
            "enabled": settings.admin_enabled,
            "loggedIn": bool(session),
            "isAdmin": is_admin,
            "role": role,
        }

    @router.get("/auth/login-url")
    async def login_url():
        return {"url": context.auth_manager.build_authorize_url()}

    @router.get("/auth/callback")
    async def auth_callback(code: str, state: str, request: Request):
        from fastapi.responses import RedirectResponse

        response = RedirectResponse(url="/")
        await context.auth_manager.handle_callback(
            code, state, response, getattr(request.state, "database", None)
        )
        return response

    # 兼容旧 callback 地址 /api/auth/callback（OAuth app 配置未更新时使用）
    legacy_auth_router = APIRouter()

    @legacy_auth_router.get("/auth/callback", include_in_schema=False)
    async def legacy_auth_callback(code: str, state: str, request: Request):
        return await auth_callback(code, state, request)

    @router.post("/auth/logout")
    async def logout(request: Request):
        from fastapi.responses import JSONResponse

        response = JSONResponse({"success": True})
        await context.auth_manager.logout_async(
            request, response, getattr(request.state, "database", None)
        )
        return response

    @router.get("/actors")
    async def list_actors(
        request: Request,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        async with request.state.database.session() as session:
            service = DBService(session)
            actors = await service.list_actors(
                role=role, is_active=is_active, limit=limit, offset=offset
            )
            return {"actors": [_serialize_actor(actor) for actor in actors], "limit": limit, "offset": offset}

    @router.put("/actors/{actor_id}")
    async def update_actor(actor_id: int, payload: ActorUpdatePayload, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            audit = AuditService(service)
            before = await service.session.get(Actor, actor_id)
            before_snapshot = _serialize_actor(before) if before else None
            actor = await service.update_actor(actor_id, **payload.model_dump(exclude_unset=True))
            if not actor:
                raise HTTPException(status_code=404, detail="actor_not_found")
            await audit.record_success(
                action="update",
                resource_type="actor",
                resource_id=actor.id,
                before=before_snapshot,
                after=_serialize_actor(actor),
            )
            return _serialize_actor(actor)

    @router.get("/app-settings")
    async def list_app_settings(request: Request, category: Optional[str] = None):
        async with request.state.database.session() as session:
            service = DBService(session)
            settings_rows = await service.list_app_settings(category)
            return {"settings": [_serialize_app_setting(row) for row in settings_rows]}

    @router.put("/app-settings/{key}")
    async def update_app_setting(key: str, payload: AppSettingPayload, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            audit = AuditService(service)
            row = await service.update_app_setting(
                key,
                payload.value,
                category=payload.category,
                description=payload.description,
            )
            await audit.record_success(
                action="update",
                resource_type="app_setting",
                resource_id=row.id,
                after=_serialize_app_setting(row),
            )
            return _serialize_app_setting(row)

    @router.delete("/app-settings/{key}")
    async def delete_app_setting(key: str, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            audit = AuditService(service)
            deleted = await service.delete_app_setting(key)
            if not deleted:
                raise HTTPException(status_code=404, detail="setting_not_found")
            await audit.record_success(
                action="delete",
                resource_type="app_setting",
                resource_id=None,
                after={"key": key},
            )
            return {"success": True}

    @router.get("/repos")
    async def list_repos(request: Request):
        session = await context.auth_manager.get_session_async(
            request, getattr(request.state, "database", None)
        )
        if context.auth_manager.enabled and session:
            client = context.auth_manager.build_user_client(session)
        else:
            client = context.gitea_client
        repos = await client.list_user_repos()
        if repos is None:
            raise HTTPException(status_code=502, detail="无法从 Gitea 获取仓库列表")
        return {"repos": [_serialize_repo(repo) for repo in repos]}

    @router.get("/repos/{owner}/{repo}/permissions")
    async def get_repo_permissions(owner: str, repo: str, request: Request):
        session = await context.auth_manager.get_session_async(
            request, getattr(request.state, "database", None)
        )
        if not session:
            raise HTTPException(status_code=401, detail="未登录")
        user_client = context.auth_manager.build_user_client(session)
        perms = await user_client.check_repo_permissions(owner, repo)
        if perms is None:
            raise HTTPException(status_code=502, detail="无法从 Gitea 获取仓库权限")
        return perms

    @router.get("/repos/{owner}/{repo}/pulls")
    async def list_pulls(owner: str, repo: str, state: str = "all", limit: int = 10):
        pulls = await context.gitea_client.list_pull_requests(owner, repo, state=state, limit=limit)
        if pulls is None:
            raise HTTPException(status_code=502, detail="无法从 Gitea 获取 PR 列表")
        return {"pulls": pulls}

    @router.get("/repos/{owner}/{repo}/webhook-status")
    async def webhook_status(owner: str, repo: str, request: Request):
        user_client = await _require_repo_admin_client(context, owner, repo, request)
        hooks = await user_client.list_repo_hooks(owner, repo) or []
        return {"configured": bool(hooks), "hooks": hooks}

    @router.post("/repos/{owner}/{repo}/webhook")
    async def configure_webhook(owner: str, repo: str, request: Request):
        payload = await request.json()
        user_client = await _require_repo_admin_client(context, owner, repo, request)
        secret = payload.get("webhook_secret") or payload.get("secret") or secrets.token_urlsafe(24)
        hook_url = _resolve_webhook_url(request, payload.get("url"))
        hook_events = _resolve_webhook_events(payload.get("events"))
        hook = {
            "type": "gitea",
            "active": True,
            "events": hook_events,
            "config": {
                "url": hook_url,
                "content_type": "json",
                "secret": secret,
            },
        }
        hook_id = await user_client.ensure_repo_webhook(owner, repo, hook)
        if hook_id is None:
            raise HTTPException(status_code=502, detail="Webhook 配置失败")
        if getattr(request.state, "database", None):
            async with request.state.database.session() as session:
                service = DBService(session)
                audit = AuditService(service)
                repo_obj = await service.update_repository_secret(owner, repo, secret)
                await audit.record_success(
                    action="update",
                    resource_type="repository",
                    resource_id=repo_obj.id if repo_obj else None,
                    after={"webhook_secret_enc": secret},
                    context={"repository_id": repo_obj.id if repo_obj else None},
                )
        return {"success": True, "hook_id": hook_id}

    @router.post("/repos/{owner}/{repo}/setup")
    async def setup_repo(owner: str, repo: str, request: Request):
        if getattr(request.state, "database", None):
            async with request.state.database.session() as session:
                service = DBService(session)
                audit = AuditService(service)
                repo_obj = await service.get_or_create_repository(owner, repo)
                await service.ensure_repository_feature(repo_obj.id, "review")
                await service.ensure_repository_feature(repo_obj.id, "issue")
                await audit.record_success(
                    action="create",
                    resource_type="repository",
                    resource_id=repo_obj.id,
                    context={"repository_id": repo_obj.id},
                )
        return {"success": True}

    @router.get("/repos/{owner}/{repo}/config-health")
    async def config_health(owner: str, repo: str, request: Request):
        if not getattr(request.state, "database", None):
            return {"checks": [], "status": "unknown"}
        from app.review.config_health import check_repo_config_health

        async with request.state.database.session() as session:
            service = DBService(session)
            return await check_repo_config_health(service, owner, repo)

    @router.get("/provider-credentials")
    async def list_provider_credentials(request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            return {"credentials": [_serialize_credential(c) for c in await service.list_provider_credentials()]}

    @router.post("/provider-credentials")
    async def create_provider_credential(payload: ProviderCredentialPayload, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            cred = await service.create_provider_credential(**payload.model_dump())
            audit = AuditService(service)
            await audit.record_success(
                action="create",
                resource_type="provider_credential",
                resource_id=cred.id,
                after=_serialize_credential(cred),
            )
            return _serialize_credential(cred)

    @router.put("/provider-credentials/{credential_id}")
    async def update_provider_credential(credential_id: int, payload: ProviderCredentialUpdatePayload, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            cred = await service.update_provider_credential(
                credential_id,
                **payload.model_dump(exclude_unset=True),
            )
            if not cred:
                raise HTTPException(status_code=404, detail="凭证不存在")
            audit = AuditService(service)
            await audit.record_success(
                action="update",
                resource_type="provider_credential",
                resource_id=cred.id,
                after=_serialize_credential(cred),
            )
            return _serialize_credential(cred)

    @router.post("/provider-credentials/{credential_id}/rotate")
    async def rotate_provider_credential(credential_id: int, payload: ProviderCredentialRotatePayload, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            cred = await service.rotate_provider_credential(credential_id, payload.api_key)
            if not cred:
                raise HTTPException(status_code=404, detail="凭证不存在")
            audit = AuditService(service)
            await audit.record_success(
                action="rotate_secret",
                resource_type="provider_credential",
                resource_id=cred.id,
                after={"api_key_enc": payload.api_key},
            )
            return _serialize_credential(cred)

    @router.delete("/provider-credentials/{credential_id}")
    async def delete_provider_credential(credential_id: int, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            try:
                deleted = await service.delete_provider_credential(credential_id)
            except ValueError as exc:
                if str(exc) == "credential_in_use":
                    raise HTTPException(status_code=409, detail="credential_in_use") from exc
                raise
            if not deleted:
                raise HTTPException(status_code=404, detail="凭证不存在")
            audit = AuditService(service)
            await audit.record_success(
                action="delete",
                resource_type="provider_credential",
                resource_id=credential_id,
            )
            return {"success": True}

    @router.get("/repos/{owner}/{repo}/configurations")
    async def get_repo_configuration(owner: str, repo: str, scenario: str, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            repo_obj = await service.get_repository(owner, repo)
            if not repo_obj:
                raise HTTPException(status_code=404, detail="仓库不存在")
            config = await service.get_repository_config(repo_obj.id, scenario)
            if not config:
                raise HTTPException(status_code=404, detail="configuration_required")
            return _serialize_repo_config(config)

    @router.put("/repos/{owner}/{repo}/configurations/{scenario}")
    async def update_repo_config(owner: str, repo: str, scenario: str, payload: RepositoryConfigUpdatePayload, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            repo_obj = await service.get_or_create_repository(owner, repo)
            config = await service.update_repository_config(
                repo_obj.id,
                scenario,
                **payload.model_dump(exclude_unset=True),
            )
            audit = AuditService(service)
            await audit.record_success(
                action="update",
                resource_type="repository_config",
                resource_id=config.id,
                after=_serialize_repo_config(config),
                context={"repository_id": repo_obj.id},
            )
            return _serialize_repo_config(config)

    @router.get("/runs")
    async def list_runs(request: Request, kind: Optional[str] = None, repository_id: Optional[int] = None, status: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        async with request.state.database.session() as session:
            service = DBService(session)
            runs = await service.list_analysis_runs(
                kind=kind, repository_id=repository_id, status=status, limit=limit, offset=offset
            )
            return {"runs": [_serialize_run(r) for r in runs], "total": len(runs), "limit": limit, "offset": offset}

    @router.get("/runs/{run_id}")
    async def get_run(run_id: int, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            run = await service.get_analysis_run(run_id)
            if not run:
                raise HTTPException(status_code=404, detail="运行记录不存在")
            return _serialize_run(run)

    @router.get("/runs/{run_id}/annotations")
    async def get_run_annotations(run_id: int, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            annotations = await service.list_analysis_annotations(run_id)
            return {"annotations": [_serialize_annotation(item) for item in annotations]}

    @router.get("/provider-runs")
    async def list_provider_runs(request: Request, provider: Optional[str] = "forge", scenario: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        async with request.state.database.session() as session:
            service = DBService(session)
            runs = await service.list_provider_runs(provider=provider, scenario=scenario, limit=limit, offset=offset)
            return {"runs": [_serialize_provider_run(r) for r in runs], "total": len(runs), "limit": limit, "offset": offset}

    @router.get("/provider-runs/{provider_session_id}")
    async def get_provider_run(provider_session_id: str, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            run = await service.get_provider_run(provider_session_id)
            if not run:
                raise HTTPException(status_code=404, detail="Provider run 不存在")
            return _serialize_provider_run(run)

    @router.get("/usage")
    async def usage(request: Request, repository_id: Optional[int] = None, actor_id: Optional[int] = None, start: Optional[date] = None, end: Optional[date] = None):
        async with request.state.database.session() as session:
            service = DBService(session)
            summary = await service.get_usage_summary(repository_id=repository_id, actor_id=actor_id, start_date=start, end_date=end)
            events = await service.list_usage_events(repository_id=repository_id, actor_id=actor_id, start_date=start, end_date=end)
            return {
                "summary": summary,
                "events": [
                    {
                        "id": e.id,
                        "analysis_run_id": e.analysis_run_id,
                        "repository_id": e.repository_id,
                        "actor_id": e.actor_id,
                        "event_date": e.event_date.isoformat(),
                        "provider": e.provider,
                        "input_tokens": e.input_tokens,
                        "output_tokens": e.output_tokens,
                        "cache_creation_input_tokens": e.cache_creation_input_tokens,
                        "cache_read_input_tokens": e.cache_read_input_tokens,
                        "gitea_api_calls": e.gitea_api_calls,
                        "provider_api_calls": e.provider_api_calls,
                        "clone_operations": e.clone_operations,
                    }
                    for e in events
                ],
            }

    @router.get("/audit-events")
    async def audit_events(
        request: Request,
        actor_id: Optional[int] = None,
        repository_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ):
        async with request.state.database.session() as session:
            service = DBService(session)
            events = await service.list_audit_events(
                limit=limit,
                offset=offset,
                actor_id=actor_id,
                repository_id=repository_id,
                resource_type=resource_type,
                action=action,
            )
            return {
                "events": [
                    {
                        "id": e.id,
                        "actor_id": e.actor_id,
                        "action": e.action,
                        "resource_type": e.resource_type,
                        "resource_id": e.resource_id,
                        "status": e.status,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in events
                ]
            }

    @router.get("/webhook-events")
    async def webhook_events(
        request: Request,
        repository_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        async with request.state.database.session() as session:
            service = DBService(session)
            events = await service.list_webhook_events(
                repository_id=repository_id, status=status, limit=limit, offset=offset
            )
            return {"events": [_serialize_webhook_event(event) for event in events], "limit": limit, "offset": offset}

    @router.get("/webhook-events/{event_id}")
    async def webhook_event_detail(event_id: int, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            event = await service.get_webhook_event(event_id)
            if not event:
                raise HTTPException(status_code=404, detail="webhook_event_not_found")
            return _serialize_webhook_event(event)

    @router.post("/webhook-events/{event_id}/replay")
    async def replay_webhook_event(event_id: int, request: Request, background_tasks: BackgroundTasks):
        async with request.state.database.session() as session:
            service = DBService(session)
            audit = AuditService(service)
            event = await service.get_webhook_event(event_id)
            if not event:
                raise HTTPException(status_code=404, detail="webhook_event_not_found")
            payload = json.loads(event.payload_json)
            await service.update_webhook_event(event.id, status="queued")
            await audit.record_success(
                action="replay_webhook",
                resource_type="webhook_event",
                resource_id=event.id,
                context={"repository_id": event.repository_id},
            )
        if event.event_type == "pull_request":
            background_tasks.add_task(context.webhook_handler.handle_pull_request, payload, None, None)
        elif event.event_type == "issues":
            background_tasks.add_task(context.webhook_handler.handle_issue, payload)
        elif event.event_type == "issue_comment":
            background_tasks.add_task(context.webhook_handler.handle_issue_comment, payload)
        return {"success": True}

    @router.get("/audit-events/{event_id}")
    async def audit_event_detail(event_id: int, request: Request):
        async with request.state.database.session() as session:
            service = DBService(session)
            event = await service.get_audit_event(event_id)
            if not event:
                raise HTTPException(status_code=404, detail="审计事件不存在")
            return {
                "id": event.id,
                "actor_id": event.actor_id,
                "actor_type": event.actor_type,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "repository_id": event.repository_id,
                "namespace_id": event.namespace_id,
                "request_id": event.request_id,
                "source": event.source,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "before": json.loads(event.before_json) if event.before_json else None,
                "after": json.loads(event.after_json) if event.after_json else None,
                "changed_fields": json.loads(event.changed_fields_json) if event.changed_fields_json else [],
                "sensitive_fields": json.loads(event.sensitive_fields_json) if event.sensitive_fields_json else [],
                "status": event.status,
                "error_message": event.error_message,
                "created_at": event.created_at.isoformat(),
            }

    @public_router.post("/webhook")
    async def webhook(request: Request, background_tasks: BackgroundTasks):
        payload = await request.json()
        event = request.headers.get("X-Gitea-Event", "")
        if event == "pull_request":
            background_tasks.add_task(context.webhook_handler.handle_pull_request, payload, None, None)
        elif event == "issues":
            background_tasks.add_task(context.webhook_handler.handle_issue, payload)
        elif event == "issue_comment":
            background_tasks.add_task(context.webhook_handler.handle_issue_comment, payload)
        return {"status": "accepted", "api": "v2"}

    return router, public_router, legacy_auth_router

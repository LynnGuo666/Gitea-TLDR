"""database v2 schema

Revision ID: d2c4b6a8e9f0
Revises: b9e4f1a2c3d5
Create Date: 2026-05-09 00:00:00.000000

"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d2c4b6a8e9f0"
down_revision: Union[str, None] = "b9e4f1a2c3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _valid_url(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value or value in {"1", "0", "true", "false"}:
        return None
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")
    return None


def _valid_model(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value or value.isdigit():
        return None
    return value


def _copy_sqlite_db() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    rows = bind.execute(sa.text("PRAGMA database_list")).fetchall()
    db_path = None
    for row in rows:
        # sqlite returns seq, name, file
        if row[1] == "main":
            db_path = row[2]
            break
    if not db_path or db_path == ":memory:" or not os.path.exists(db_path):
        return
    src = Path(db_path)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    shutil.copy2(src, src.with_name(f"{src.name}.bak.{stamp}"))


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _table_count(table: str) -> int:
    if not _has_table(table):
        return 0
    bind = op.get_bind()
    return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)


def _source_table(name: str) -> str | None:
    legacy = f"legacy_{name}"
    if _has_table(legacy):
        return legacy
    if _has_table(name):
        return name
    return None


def _drop_indexes(table_name: str) -> None:
    """SQLite rename table 后索引名仍在全库占用；创建最终表前清理。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    for index in inspector.get_indexes(table_name):
        name = index.get("name")
        if name:
            op.drop_index(name, table_name=table_name)


def _create_v2_tables() -> None:
    # 历史模型（ConfigTemplate、Namespace）已被后续迁移移除，无法再从
    # app.models.schema 导入。这里用内联的 Table 定义保证该迁移在全新库
    # 上仍可执行 —— 这些表会在 d2c4b6a8e9f0 本身或后续迁移中被删除/重建，
    # 因此仅需要短暂存在以承接旧数据迁移。
    from sqlalchemy import (
        Column,
        DateTime,
        Integer,
        String,
        Table,
        Text,
        UniqueConstraint,
    )

    bind = op.get_bind()
    metadata = sa.MetaData()

    namespace_table = Table(
        "namespaces",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("provider", String(50), nullable=False),
        Column("name", String(255), nullable=False),
        Column("kind", String(50), nullable=False),
        Column("display_name", String(255), nullable=True),
        Column("created_at", DateTime, nullable=True),
        Column("updated_at", DateTime, nullable=True),
        UniqueConstraint("provider", "name", name="uq_namespaces_provider_name"),
    )

    config_template_table = Table(
        "config_templates",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("name", String(150), nullable=False),
        Column("engine", String(100), nullable=False),
        Column("model", String(200), nullable=True),
        Column("api_url", String(500), nullable=True),
        Column("api_key_enc", Text, nullable=True),
        Column("wire_api", String(50), nullable=True),
        Column("temperature", sa.Float, nullable=True),
        Column("max_tokens", Integer, nullable=True),
        Column("custom_prompt", Text, nullable=True),
        Column("focus_json", Text, nullable=True),
        Column("features_json", Text, nullable=True),
        Column("is_active", sa.Boolean, nullable=False, default=sa.true()),
        Column("created_at", DateTime, nullable=True),
        Column("updated_at", DateTime, nullable=True),
        UniqueConstraint("name", name="uq_config_templates_name"),
    )

    from app.models.schema import (
        Actor,
        AnalysisAnnotation,
        AnalysisRun,
        AppSetting,
        AuditEvent,
        AuthSession,
        ProviderCredential,
        ProviderRun,
        Repository,
        RepositoryConfig,
        RepositoryFeature,
        UsageEvent,
        WebhookEvent,
    )

    # 先建 namespaces / config_templates（旧表，仅用于承接历史数据），
    # 再建当前 schema 模型表。checkfirst 保证已存在的表不会被重建。
    namespace_table.create(bind, checkfirst=True)
    config_template_table.create(bind, checkfirst=True)
    for model in [
        Actor,
        AuthSession,
        AppSetting,
        Repository,
        RepositoryFeature,
        ProviderCredential,
        RepositoryConfig,
        AnalysisRun,
        AnalysisAnnotation,
        ProviderRun,
        UsageEvent,
        WebhookEvent,
        AuditEvent,
    ]:
        model.__table__.create(bind, checkfirst=True)


def _ensure_system_actor() -> int:
    bind = op.get_bind()
    now = _now()
    row = bind.execute(
        sa.text(
            "SELECT id FROM actors WHERE external_provider='system' "
            "AND external_username='system'"
        )
    ).fetchone()
    if row:
        return int(row[0])
    result = bind.execute(
        sa.text(
            """
            INSERT INTO actors (
                external_provider, external_username, display_name, email, role,
                permissions_json, is_active, last_login_at, created_at, updated_at
            )
            VALUES (
                'system', 'system', 'System', NULL, 'system',
                NULL, 1, NULL, :now, :now
            )
            """
        ),
        {"now": now},
    )
    return int(result.lastrowid)


def _migrate_actors(system_actor_id: int) -> dict[int, int]:
    bind = op.get_bind()
    mapping: dict[int, int] = {}
    source_table = _source_table("users")
    if not source_table:
        return mapping
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        username = row["username"]
        existing = bind.execute(
            sa.text(
                "SELECT id FROM actors WHERE external_provider='gitea' "
                "AND external_username=:username"
            ),
            {"username": username},
        ).fetchone()
        if existing:
            actor_id = int(existing[0])
        else:
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO actors (
                        external_provider, external_username, display_name, email,
                        role, permissions_json, is_active, last_login_at,
                        created_at, updated_at
                    )
                    VALUES (
                        'gitea', :username, :username, :email, :role, :permissions,
                        :is_active, :last_login_at, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "username": username,
                    "email": row.get("email"),
                    "role": row.get("role") or "user",
                    "permissions": row.get("permissions"),
                    "is_active": row.get("is_active", True),
                    "last_login_at": row.get("last_login_at"),
                    "created_at": row.get("created_at") or _now(),
                    "updated_at": row.get("updated_at") or _now(),
                },
            )
            actor_id = int(result.lastrowid)
        mapping[int(row["id"])] = actor_id
    mapping.setdefault(0, system_actor_id)
    return mapping


def _migrate_sessions(actor_map: dict[int, int]) -> None:
    bind = op.get_bind()
    source_table = _source_table("user_sessions")
    if not source_table:
        return
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        token_hash = hashlib.sha256(row["session_id"].encode("utf-8")).hexdigest()
        exists = bind.execute(
            sa.text("SELECT id FROM auth_sessions WHERE session_token_hash=:hash"),
            {"hash": token_hash},
        ).fetchone()
        if exists:
            continue
        expires_at = datetime.fromtimestamp(float(row["expires_at"]), tz=timezone.utc)
        bind.execute(
            sa.text(
                """
                INSERT INTO auth_sessions (
                    session_token_hash, actor_id, access_token_enc, refresh_token_enc,
                    scopes_json, user_info_json, expires_at, revoked_at,
                    created_at, updated_at
                )
                VALUES (
                    :hash, :actor_id, :access_token, :refresh_token, :scopes,
                    :user_info, :expires_at, NULL, :created_at, :updated_at
                )
                """
            ),
            {
                "hash": token_hash,
                "actor_id": actor_map.get(row.get("user_id")),
                "access_token": row["access_token"],
                "refresh_token": row.get("refresh_token"),
                "scopes": _json(
                    [
                        scope
                        for scope in (row.get("scope") or "").replace(",", " ").split()
                        if scope
                    ]
                ),
                "user_info": row.get("user_info"),
                "expires_at": expires_at.replace(tzinfo=None),
                "created_at": row.get("created_at") or _now(),
                "updated_at": row.get("updated_at") or _now(),
            },
        )


def _migrate_settings(system_actor_id: int) -> None:
    bind = op.get_bind()
    source_table = _source_table("admin_settings")
    if not source_table:
        return
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        exists = bind.execute(
            sa.text("SELECT id FROM app_settings WHERE key=:key"),
            {"key": row["key"]},
        ).fetchone()
        if exists:
            continue
        value = row["value"]
        try:
            json.loads(value)
            value_json = value
        except Exception:
            value_json = _json(value)
        bind.execute(
            sa.text(
                """
                INSERT INTO app_settings (
                    key, category, value_json, description, updated_by_actor_id,
                    created_at, updated_at
                )
                VALUES (
                    :key, :category, :value_json, :description, :actor_id,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "key": row["key"],
                "category": row["category"],
                "value_json": value_json,
                "description": row.get("description"),
                "actor_id": system_actor_id,
                "created_at": row.get("created_at") or _now(),
                "updated_at": row.get("updated_at") or _now(),
            },
        )


def _migrate_repositories() -> dict[int, int]:
    bind = op.get_bind()
    mapping: dict[int, int] = {}
    source_table = _source_table("repositories")
    if not _has_table(source_table):
        return mapping
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        owner = row["owner"]
        repo_name = row["repo_name"]
        ns = bind.execute(
            sa.text("SELECT id FROM namespaces WHERE provider='gitea' AND name=:name"),
            {"name": owner},
        ).fetchone()
        if ns:
            namespace_id = int(ns[0])
        else:
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO namespaces (
                        provider, name, kind, display_name, created_at, updated_at
                    )
                    VALUES ('gitea', :name, 'unknown', :name, :now, :now)
                    """
                ),
                {"name": owner, "now": _now()},
            )
            namespace_id = int(result.lastrowid)

        existing = bind.execute(
            sa.text(
                "SELECT id FROM repositories "
                "WHERE provider='gitea' AND owner=:owner AND name=:name"
            ),
            {"owner": owner, "name": repo_name},
        ).fetchone()
        if existing:
            repo_id = int(existing[0])
        else:
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO repositories (
                        provider, namespace_id, owner, name, full_name,
                        webhook_secret_enc, is_active, created_at, updated_at
                    )
                    VALUES (
                        'gitea', :namespace_id, :owner, :name, :full_name,
                        :webhook_secret, :is_active, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "namespace_id": namespace_id,
                    "owner": owner,
                    "name": repo_name,
                    "full_name": f"{owner}/{repo_name}",
                    "webhook_secret": row.get("webhook_secret"),
                    "is_active": row.get("is_active", True),
                    "created_at": row.get("created_at") or _now(),
                    "updated_at": row.get("updated_at") or _now(),
                },
            )
            repo_id = int(result.lastrowid)

        mapping[int(row["id"])] = repo_id
        for scenario, enabled, auto, manual in [
            ("review", True, True, True),
            (
                "issue",
                row.get("issue_enabled", True),
                row.get("issue_auto_on_open", True),
                row.get("issue_manual_command_enabled", True),
            ),
        ]:
            exists = bind.execute(
                sa.text(
                    "SELECT id FROM repository_features "
                    "WHERE repository_id=:repo_id AND scenario=:scenario"
                ),
                {"repo_id": repo_id, "scenario": scenario},
            ).fetchone()
            if not exists:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO repository_features (
                            repository_id, scenario, enabled, auto_on_open,
                            manual_command_enabled, created_at, updated_at
                        )
                        VALUES (
                            :repo_id, :scenario, :enabled, :auto_on_open,
                            :manual, :now, :now
                        )
                        """
                    ),
                    {
                        "repo_id": repo_id,
                        "scenario": scenario,
                        "enabled": enabled,
                        "auto_on_open": auto,
                        "manual": manual,
                        "now": _now(),
                    },
                )
    return mapping


def _credential_for(
    *,
    scope_key: str,
    name: str,
    provider: str,
    api_url: str | None,
    api_key: str | None,
    system_actor_id: int,
) -> int | None:
    bind = op.get_bind()
    if not api_url and not api_key:
        return None
    safe_url = _valid_url(api_url)
    row = bind.execute(
        sa.text(
            "SELECT id FROM provider_credentials "
            "WHERE scope_key=:scope_key AND name=:name"
        ),
        {"scope_key": scope_key, "name": name},
    ).fetchone()
    if row:
        return int(row[0])
    result = bind.execute(
        sa.text(
            """
            INSERT INTO provider_credentials (
                scope_type, scope_key, namespace_id, name, provider, api_url,
                api_key_enc, is_active, created_by_actor_id, last_used_at,
                created_at, updated_at
            )
            VALUES (
                :scope_type, :scope_key, NULL, :name, :provider, :api_url,
                :api_key, 1, :actor_id, NULL, :now, :now
            )
            """
        ),
        {
            "scope_type": "system" if scope_key == "system" else "repository",
            "scope_key": scope_key,
            "name": name,
            "provider": provider,
            "api_url": safe_url,
            "api_key": api_key,
            "actor_id": system_actor_id,
            "now": _now(),
        },
    )
    return int(result.lastrowid)


def _migrate_configs(repo_map: dict[int, int], system_actor_id: int) -> None:
    bind = op.get_bind()
    scenarios = [
        ("model_configs", "review", "claude_code", "default_features", "default_focus"),
        ("issue_configs", "issue", "forge", None, "default_focus"),
    ]
    for table, scenario, default_engine, features_col, focus_col in scenarios:
        source_table = _source_table(table)
        if not source_table:
            continue
        rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
        for row in rows:
            old_repo_id = row.get("repository_id")
            repo_id = (
                repo_map.get(int(old_repo_id)) if old_repo_id is not None else None
            )
            engine = row.get("engine") or default_engine
            model = _valid_model(row.get("model"))
            scope_key = "system" if repo_id is None else f"repo:{repo_id}"
            cred = _credential_for(
                scope_key=scope_key,
                name=f"{scenario}-{engine}-credential",
                provider="anthropic"
                if engine in {"claude_code", "forge"}
                else "custom",
                api_url=row.get("api_url"),
                api_key=row.get("api_key"),
                system_actor_id=system_actor_id,
            )
            focus = row.get(focus_col) if focus_col else None
            features = row.get(features_col) if features_col else None
            if repo_id is None:
                exists = bind.execute(
                    sa.text(
                        "SELECT id FROM config_templates "
                        "WHERE scope_key='system' AND scenario=:scenario AND name=:name"
                    ),
                    {
                        "scenario": scenario,
                        "name": row.get("config_name") or f"default-{scenario}",
                    },
                ).fetchone()
                if exists:
                    continue
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO config_templates (
                            scope_type, scope_key, namespace_id, scenario, name,
                            engine, model, credential_id, wire_api, temperature,
                            max_tokens, custom_prompt, focus_json, features_json,
                            is_default, is_active, created_by_actor_id,
                            created_at, updated_at
                        )
                        VALUES (
                            'system', 'system', NULL, :scenario, :name,
                            :engine, :model, :credential_id, :wire_api,
                            :temperature, :max_tokens, :custom_prompt, :focus,
                            :features, :is_default, 1, :actor_id,
                            :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "scenario": scenario,
                        "name": row.get("config_name") or f"default-{scenario}",
                        "engine": engine,
                        "model": model,
                        "credential_id": cred,
                        "wire_api": row.get("wire_api"),
                        "temperature": row.get("temperature"),
                        "max_tokens": row.get("max_tokens"),
                        "custom_prompt": row.get("custom_prompt"),
                        "focus": focus,
                        "features": features,
                        "is_default": row.get("is_default", True),
                        "actor_id": system_actor_id,
                        "created_at": row.get("created_at") or _now(),
                        "updated_at": row.get("updated_at") or _now(),
                    },
                )
            else:
                exists = bind.execute(
                    sa.text(
                        "SELECT id FROM repository_configs "
                        "WHERE repository_id=:repo_id AND scenario=:scenario"
                    ),
                    {"repo_id": repo_id, "scenario": scenario},
                ).fetchone()
                if exists:
                    continue
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO repository_configs (
                            repository_id, scenario, source_template_id,
                            template_version_copied_at, engine, model, credential_id,
                            api_url_override, wire_api, temperature, max_tokens,
                            custom_prompt, focus_json, features_json, is_active,
                            created_by_actor_id, created_at, updated_at
                        )
                        VALUES (
                            :repo_id, :scenario, NULL, NULL, :engine, :model,
                            :credential_id, NULL, :wire_api, :temperature,
                            :max_tokens, :custom_prompt, :focus, :features,
                            1, :actor_id, :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "repo_id": repo_id,
                        "scenario": scenario,
                        "engine": engine,
                        "model": model,
                        "credential_id": cred,
                        "wire_api": row.get("wire_api"),
                        "temperature": row.get("temperature"),
                        "max_tokens": row.get("max_tokens"),
                        "custom_prompt": row.get("custom_prompt"),
                        "focus": focus,
                        "features": features,
                        "actor_id": system_actor_id,
                        "created_at": row.get("created_at") or _now(),
                        "updated_at": row.get("updated_at") or _now(),
                    },
                )


def _migrate_runs(repo_map: dict[int, int]) -> dict[tuple[str, int], int]:
    bind = op.get_bind()
    run_map: dict[tuple[str, int], int] = {}
    sources = [
        (
            "review_sessions",
            "review",
            "pr_number",
            "pr_title",
            "pr_author",
            None,
        ),
        (
            "issue_sessions",
            "issue",
            "issue_number",
            "issue_title",
            "issue_author",
            "issue_state",
        ),
    ]
    for table, kind, number_col, title_col, author_col, state_col in sources:
        source_table = _source_table(table)
        if not source_table:
            continue
        rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
        for row in rows:
            repo_id = repo_map.get(int(row["repository_id"]))
            if not repo_id:
                continue
            completed_at = row.get("completed_at")
            success = row.get("overall_success")
            status = (
                "running"
                if not completed_at
                else ("completed" if success else "failed")
            )
            payload: dict[str, object] = {}
            if kind == "review":
                for key in [
                    "enabled_features",
                    "focus_areas",
                    "analysis_mode",
                    "diff_size_bytes",
                    "inline_comments_count",
                ]:
                    payload[key] = row.get(key)
            else:
                try:
                    payload = json.loads(row.get("analysis_payload") or "{}")
                    if not isinstance(payload, dict):
                        payload = {"analysis_payload": row.get("analysis_payload")}
                except Exception:
                    payload = {"analysis_payload": row.get("analysis_payload")}
            result = bind.execute(
                sa.text(
                    """
                    INSERT INTO analysis_runs (
                        kind, repository_id, external_number, external_title,
                        external_author, external_state, source_branch, target_branch,
                        head_sha, trigger_type, source_comment_id, bot_comment_id,
                        effective_engine, effective_model, repository_config_id,
                        credential_id, status, overall_success, overall_severity,
                        summary_markdown, result_payload_json, error_message,
                        started_at, completed_at, duration_seconds,
                        created_at, updated_at
                    )
                    VALUES (
                        :kind, :repo_id, :external_number, :external_title,
                        :external_author, :external_state, :source_branch,
                        :target_branch, :head_sha, :trigger_type, :source_comment_id,
                        :bot_comment_id, :engine, :model, NULL, NULL, :status,
                        :overall_success, :overall_severity, :summary_markdown,
                        :payload, :error_message, :started_at, :completed_at,
                        :duration_seconds, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "kind": kind,
                    "repo_id": repo_id,
                    "external_number": row[number_col],
                    "external_title": row.get(title_col),
                    "external_author": row.get(author_col),
                    "external_state": row.get(state_col) if state_col else None,
                    "source_branch": row.get("head_branch"),
                    "target_branch": row.get("base_branch"),
                    "head_sha": row.get("head_sha"),
                    "trigger_type": row.get("trigger_type") or "manual",
                    "source_comment_id": row.get("source_comment_id"),
                    "bot_comment_id": row.get("bot_comment_id"),
                    "engine": row.get("engine"),
                    "model": row.get("model"),
                    "status": status,
                    "overall_success": success,
                    "overall_severity": row.get("overall_severity"),
                    "summary_markdown": row.get("summary_markdown"),
                    "payload": _json(payload),
                    "error_message": row.get("error_message"),
                    "started_at": row.get("started_at") or _now(),
                    "completed_at": completed_at,
                    "duration_seconds": row.get("duration_seconds"),
                    "created_at": row.get("started_at") or _now(),
                    "updated_at": completed_at or row.get("started_at") or _now(),
                },
            )
            run_map[(kind, int(row["id"]))] = int(result.lastrowid)
    return run_map


def _migrate_annotations(run_map: dict[tuple[str, int], int]) -> None:
    bind = op.get_bind()
    source_table = _source_table("inline_comments")
    if not source_table:
        return
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        run_id = run_map.get(("review", int(row["review_session_id"])))
        if not run_id:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO analysis_annotations (
                    analysis_run_id, annotation_type, file_path, new_line, old_line,
                    severity, body, suggestion, created_at
                )
                VALUES (
                    :run_id, 'inline_comment', :file_path, :new_line, :old_line,
                    :severity, :body, :suggestion, :created_at
                )
                """
            ),
            {
                "run_id": run_id,
                "file_path": row["file_path"],
                "new_line": row.get("new_line"),
                "old_line": row.get("old_line"),
                "severity": row.get("severity"),
                "body": row["comment"],
                "suggestion": row.get("suggestion"),
                "created_at": row.get("created_at") or _now(),
            },
        )


def _migrate_provider_runs(
    repo_map: dict[int, int], run_map: dict[tuple[str, int], int]
) -> dict[int, int]:
    bind = op.get_bind()
    mapping: dict[int, int] = {}
    source_table = _source_table("forge_sessions")
    if not source_table:
        return mapping
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        old_review_id = row.get("review_session_id")
        old_issue_id = row.get("issue_session_id")
        run_id = None
        if old_review_id is not None:
            run_id = run_map.get(("review", int(old_review_id)))
        if run_id is None and old_issue_id is not None:
            run_id = run_map.get(("issue", int(old_issue_id)))
        repo_id = (
            repo_map.get(int(row["repository_id"]))
            if row.get("repository_id")
            else None
        )
        result = bind.execute(
            sa.text(
                """
                INSERT INTO provider_runs (
                    analysis_run_id, repository_id, provider, provider_session_id,
                    scenario, status, model, turns, tool_calls_count, messages_json,
                    input_tokens, output_tokens, cache_creation_input_tokens,
                    cache_read_input_tokens, started_at, completed_at,
                    duration_seconds, error_message, created_at, updated_at
                )
                VALUES (
                    :run_id, :repo_id, 'forge', :session_id, :scenario, :status,
                    :model, :turns, :tool_calls_count, :messages_json,
                    :input_tokens, :output_tokens, :cache_creation, :cache_read,
                    :started_at, :completed_at, :duration_seconds, :error,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "run_id": run_id,
                "repo_id": repo_id,
                "session_id": row["session_id"],
                "scenario": row["scenario"],
                "status": row["status"],
                "model": row.get("model"),
                "turns": row.get("turns") or 0,
                "tool_calls_count": row.get("tool_calls_count") or 0,
                "messages_json": row.get("messages_json"),
                "input_tokens": row.get("input_tokens") or 0,
                "output_tokens": row.get("output_tokens") or 0,
                "cache_creation": row.get("cache_creation_input_tokens") or 0,
                "cache_read": row.get("cache_read_input_tokens") or 0,
                "started_at": row.get("started_at") or _now(),
                "completed_at": row.get("completed_at"),
                "duration_seconds": row.get("duration_seconds"),
                "error": row.get("error"),
                "created_at": row.get("started_at") or _now(),
                "updated_at": row.get("completed_at")
                or row.get("started_at")
                or _now(),
            },
        )
        mapping[int(row["id"])] = int(result.lastrowid)
    return mapping


def _migrate_usage(
    repo_map: dict[int, int], actor_map: dict[int, int], run_map
) -> None:
    bind = op.get_bind()
    source_table = _source_table("usage_stats")
    if not source_table:
        return
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        repo_id = repo_map.get(int(row["repository_id"]))
        if not repo_id:
            continue
        run_id = None
        if row.get("review_session_id") is not None:
            run_id = run_map.get(("review", int(row["review_session_id"])))
        if run_id is None and row.get("issue_session_id") is not None:
            run_id = run_map.get(("issue", int(row["issue_session_id"])))
        bind.execute(
            sa.text(
                """
                INSERT INTO usage_events (
                    analysis_run_id, provider_run_id, repository_id, actor_id,
                    event_date, provider, input_tokens, output_tokens,
                    cache_creation_input_tokens, cache_read_input_tokens,
                    gitea_api_calls, provider_api_calls, clone_operations, created_at
                )
                VALUES (
                    :run_id, NULL, :repo_id, :actor_id, :event_date, :provider,
                    :input_tokens, :output_tokens, :cache_creation, :cache_read,
                    :gitea_calls, :provider_calls, :clone_ops, :created_at
                )
                """
            ),
            {
                "run_id": run_id,
                "repo_id": repo_id,
                "actor_id": actor_map.get(row.get("user_id")),
                "event_date": row["stat_date"],
                "provider": None,
                "input_tokens": row.get("estimated_input_tokens") or 0,
                "output_tokens": row.get("estimated_output_tokens") or 0,
                "cache_creation": row.get("cache_creation_input_tokens") or 0,
                "cache_read": row.get("cache_read_input_tokens") or 0,
                "gitea_calls": row.get("gitea_api_calls") or 0,
                "provider_calls": row.get("provider_api_calls") or 0,
                "clone_ops": row.get("clone_operations") or 0,
                "created_at": row.get("created_at") or _now(),
            },
        )


def _migrate_webhooks(repo_map: dict[int, int]) -> None:
    bind = op.get_bind()
    source_table = _source_table("webhook_logs")
    if not source_table:
        return
    rows = bind.execute(sa.text(f"SELECT * FROM {source_table}")).mappings().all()
    for row in rows:
        repo_id = repo_map.get(int(row["repository_id"]))
        if not repo_id:
            continue
        exists = bind.execute(
            sa.text("SELECT id FROM webhook_events WHERE request_id=:request_id"),
            {"request_id": row["request_id"]},
        ).fetchone()
        if exists:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO webhook_events (
                    request_id, repository_id, analysis_run_id, event_type,
                    payload_json, status, error_message, processing_time_ms,
                    retry_count, created_at, updated_at
                )
                VALUES (
                    :request_id, :repo_id, NULL, :event_type, :payload, :status,
                    :error_message, :processing_time_ms, :retry_count,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "request_id": row["request_id"],
                "repo_id": repo_id,
                "event_type": row["event_type"],
                "payload": row["payload"],
                "status": row["status"],
                "error_message": row.get("error_message"),
                "processing_time_ms": row.get("processing_time_ms") or 0,
                "retry_count": row.get("retry_count") or 0,
                "created_at": row.get("created_at") or _now(),
                "updated_at": row.get("updated_at") or _now(),
            },
        )


def _audit_migration(system_actor_id: int, before: dict[str, int]) -> None:
    bind = op.get_bind()
    after = {
        "actors": _table_count("actors"),
        "repositories": _table_count("repositories"),
        "analysis_runs": _table_count("analysis_runs"),
        "provider_runs": _table_count("provider_runs"),
        "usage_events": _table_count("usage_events"),
        "webhook_events": _table_count("webhook_events"),
    }
    bind.execute(
        sa.text(
            """
            INSERT INTO audit_events (
                actor_id, actor_type, action, resource_type, resource_id,
                repository_id, request_id, source, ip_address,
                user_agent, before_json, after_json,
                status, error_message, created_at
            )
            VALUES (
                :actor_id, 'migration', 'run_migration', 'migration', NULL,
                NULL, :request_id, 'migration', NULL, NULL,
                :before_json, :after_json,
                'success', NULL, :created_at
            )
            """
        ),
        {
            "actor_id": system_actor_id,
            "request_id": revision,
            "before_json": _json(before),
            "after_json": _json(after),
            "created_at": _now(),
        },
    )


def upgrade() -> None:
    _copy_sqlite_db()
    before = {
        "users": _table_count("users"),
        "repositories": _table_count("repositories"),
        "review_sessions": _table_count("review_sessions"),
        "issue_sessions": _table_count("issue_sessions"),
        "forge_sessions": _table_count("forge_sessions"),
        "usage_stats": _table_count("usage_stats"),
        "webhook_logs": _table_count("webhook_logs"),
    }
    # 内部表名直接使用最终名称；旧表仅作为迁移源保留为 legacy_*。
    for old_name in [
        "repositories",
        "users",
        "user_sessions",
        "admin_settings",
        "model_configs",
        "issue_configs",
        "review_sessions",
        "issue_sessions",
        "inline_comments",
        "forge_sessions",
        "usage_stats",
        "webhook_logs",
        "api_keys",
    ]:
        if _has_table(old_name) and not _has_table(f"legacy_{old_name}"):
            op.rename_table(old_name, f"legacy_{old_name}")
            _drop_indexes(f"legacy_{old_name}")

    _create_v2_tables()
    system_actor_id = _ensure_system_actor()
    actor_map = _migrate_actors(system_actor_id)
    _migrate_sessions(actor_map)
    _migrate_settings(system_actor_id)
    repo_map = _migrate_repositories()
    _migrate_configs(repo_map, system_actor_id)
    run_map = _migrate_runs(repo_map)
    _migrate_annotations(run_map)
    _migrate_provider_runs(repo_map, run_map)
    _migrate_usage(repo_map, actor_map, run_map)
    _migrate_webhooks(repo_map)
    _audit_migration(system_actor_id, before)


def downgrade() -> None:
    # 迁移会保留旧表；降级只删除当前 schema 表。
    for table in [
        "audit_events",
        "webhook_events",
        "usage_events",
        "provider_runs",
        "analysis_annotations",
        "analysis_runs",
        "repository_configs",
        "config_templates",
        "provider_credentials",
        "repository_features",
        "repositories",
        "namespaces",
        "app_settings",
        "auth_sessions",
        "actors",
    ]:
        op.drop_table(table)

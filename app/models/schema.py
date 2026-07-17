"""数据库领域模型。

当前 schema 以组织使用场景为核心：
- 模板只作为仓库配置初始化来源；
- 运行时只读取仓库独立配置；
- API Key 只存在于 provider_credentials；
- 所有写操作写入 audit_events。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import encryption_service

from .base import Base, TimestampMixin


# WebhookEvent.status 取值集合（无 DB 级枚举约束，仅在应用层统一）。
# 入口落库为 QUEUED；处理中转为 PROCESSING；重试中为 RETRYING；
# 终态为 SUCCESS / ERROR。恢复逻辑会捞取所有非终态事件。
WEBHOOK_STATUS_QUEUED = "queued"
WEBHOOK_STATUS_PROCESSING = "processing"
WEBHOOK_STATUS_RETRYING = "retrying"
WEBHOOK_STATUS_SUCCESS = "success"
WEBHOOK_STATUS_ERROR = "error"

# 可被 _recover_pending_webhooks 恢复的中间状态（不含终态 success/error）。
WEBHOOK_PENDING_STATUSES = (
    WEBHOOK_STATUS_QUEUED,
    WEBHOOK_STATUS_PROCESSING,
    WEBHOOK_STATUS_RETRYING,
)


class Actor(Base, TimestampMixin):
    """系统行为主体，包含用户、管理员和 system actor。"""

    __tablename__ = "actors"
    __table_args__ = (
        UniqueConstraint(
            "external_provider",
            "external_username",
            name="uq_actors_external_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_username: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    permissions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuthSession(Base, TimestampMixin):
    """登录会话。cookie token 只存 hash。"""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    access_token_enc: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scopes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_info_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    actor: Mapped[Optional[Actor]] = relationship("Actor")

    @property
    def access_token(self) -> str:
        return encryption_service.decrypt(self.access_token_enc)

    @access_token.setter
    def access_token(self, value: str) -> None:
        self.access_token_enc = encryption_service.encrypt(value)

    @property
    def refresh_token(self) -> Optional[str]:
        if not self.refresh_token_enc:
            return None
        return encryption_service.decrypt(self.refresh_token_enc)

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]) -> None:
        self.refresh_token_enc = encryption_service.encrypt(value) if value else value


class AppSetting(Base, TimestampMixin):
    """系统运行设置，value_json 统一保存 JSON 文本。"""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by_actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL"), nullable=True
    )


class Repository(Base, TimestampMixin):
    """仓库主体表。"""

    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("provider", "owner", "name", name="uq_repositories_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), default="gitea", nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(511), nullable=False, index=True)
    webhook_secret_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def webhook_secret(self) -> Optional[str]:
        if not self.webhook_secret_enc:
            return None
        return encryption_service.decrypt(self.webhook_secret_enc)

    @webhook_secret.setter
    def webhook_secret(self, value: Optional[str]) -> None:
        self.webhook_secret_enc = encryption_service.encrypt(value) if value else value


class RepositoryFeature(Base, TimestampMixin):
    """仓库按场景的功能开关。"""

    __tablename__ = "repository_features"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "scenario", name="uq_repository_features_scenario"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_on_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    manual_command_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )


class ProviderCredential(Base, TimestampMixin):
    """Provider 凭证，唯一保存 API key 的业务表。"""

    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("scope_key", "name", name="uq_provider_credentials_scope_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    api_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL"), nullable=True
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def api_key(self) -> Optional[str]:
        if not self.api_key_enc:
            return None
        return encryption_service.decrypt(self.api_key_enc)

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        self.api_key_enc = encryption_service.encrypt(value) if value else value



class RepositoryConfig(Base, TimestampMixin):
    """仓库真正运行时使用的独立配置。"""

    __tablename__ = "repository_configs"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "scenario", name="uq_repository_configs_scenario"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    engine: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    credential_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True
    )
    api_url_override: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    wire_api: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    custom_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    focus_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    features_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL"), nullable=True
    )

    credential: Mapped[Optional[ProviderCredential]] = relationship(
        "ProviderCredential"
    )

    @property
    def api_url(self) -> Optional[str]:
        if self.api_url_override:
            return self.api_url_override
        return self.credential.api_url if self.credential else None

    @api_url.setter
    def api_url(self, value: Optional[str]) -> None:
        self.api_url_override = value

    @property
    def api_key(self) -> Optional[str]:
        return self.credential.api_key if self.credential else None

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        if self.credential:
            self.credential.api_key = value

    def get_features(self) -> list[str]:
        import json

        if not self.features_json:
            return ["comment"]
        try:
            data = json.loads(self.features_json)
            return data if isinstance(data, list) else ["comment"]
        except (TypeError, json.JSONDecodeError):
            return ["comment"]

    def set_features(self, features: list[str]) -> None:
        import json

        self.features_json = json.dumps(features, ensure_ascii=False)

    def get_focus(self) -> list[str]:
        import json

        if not self.focus_json:
            return ["quality", "security", "performance", "logic"]
        try:
            data = json.loads(self.focus_json)
            return data if isinstance(data, list) else []
        except (TypeError, json.JSONDecodeError):
            return []

    def set_focus(self, focus: list[str]) -> None:
        import json

        self.focus_json = json.dumps(focus, ensure_ascii=False)


class AnalysisRun(Base, TimestampMixin):
    """统一分析运行记录。"""

    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    external_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    external_author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    head_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_comment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bot_comment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    effective_engine: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    effective_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    repository_config_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repository_configs.id", ondelete="SET NULL"), nullable=True
    )
    credential_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("provider_credentials.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    overall_success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    overall_severity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    summary_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    repository: Mapped[Repository] = relationship("Repository")

    def get_analysis_payload(self) -> dict:
        import json

        if not self.result_payload_json:
            return {}
        try:
            data = json.loads(self.result_payload_json)
            return data if isinstance(data, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def get_features(self) -> list[str]:
        data = self.get_analysis_payload()
        features = data.get("enabled_features")
        return features if isinstance(features, list) else []

    def get_focus(self) -> list[str]:
        data = self.get_analysis_payload()
        focus = data.get("focus_areas")
        return focus if isinstance(focus, list) else []


class AnalysisAnnotation(Base):
    """分析产生的结构化注释或行级评论。"""

    __tablename__ = "analysis_annotations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    annotation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    new_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    old_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProviderRun(Base, TimestampMixin):
    """Provider 执行明细。"""

    __tablename__ = "provider_runs"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_session_id", name="uq_provider_runs_session"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider_session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_creation_input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    cache_read_input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    repository: Mapped[Optional[Repository]] = relationship("Repository")

    @property
    def session_id(self) -> str:
        return self.provider_session_id


class UsageEvent(Base):
    """用量明细事件。"""

    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_creation_input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    cache_read_input_tokens: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    gitea_api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clone_operations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class WebhookEvent(Base, TimestampMixin):
    """Webhook 事件处理记录。"""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    analysis_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AuditEvent(Base):
    """所有写操作的审计事件。"""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("actors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repository_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

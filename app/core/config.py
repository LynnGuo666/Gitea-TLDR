"""
配置管理模块
"""

from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Gitea配置
    gitea_url: str = Field(..., description="Gitea服务器URL")
    gitea_token: str = Field(..., description="Gitea访问令牌")

    # Webhook配置
    webhook_secret: Optional[str] = Field(None, description="Webhook密钥用于验证请求")

    # Claude Code配置
    claude_code_path: str = Field("claude", description="Claude Code CLI路径")

    # Codex CLI配置
    codex_cli_path: str = Field("codex", description="Codex CLI路径")

    # 审查引擎配置
    default_provider: str = Field("claude_code", description="默认审查引擎提供者")

    # 工作目录配置
    work_dir: str = Field("/tmp/gitea-pr-reviewer", description="临时工作目录")

    # 数据库配置
    database_url: Optional[str] = Field(
        None, description="数据库连接URL，默认为工作目录下的SQLite文件"
    )

    @property
    def effective_database_url(self) -> str:
        """获取实际的数据库URL，如果未配置则使用默认SQLite路径"""
        if self.database_url:
            return self.database_url
        return f"sqlite+aiosqlite:///{self.work_dir}/gitea_pr_reviewer.db"

    # 服务器配置
    host: str = Field("0.0.0.0", description="服务器监听地址")
    port: int = Field(8000, description="服务器端口")

    # 日志配置
    log_level: str = Field("INFO", description="日志级别")

    # Debug模式
    debug: bool = Field(False, description="Debug模式，开启后输出详细日志")

    # Bot配置
    bot_username: Optional[str] = Field(None, description="Bot用户名，用于识别@提及")

    # 审查配置
    default_review_focus: list[str] = Field(
        default=["quality", "security", "performance", "logic"],
        description="默认审查重点",
    )

    # 自动请求审查者
    auto_request_reviewer: bool = Field(
        True, description="创建review后是否自动将bot设置为审查者"
    )

    # OAuth 配置
    oauth_client_id: Optional[str] = Field(None, description="Gitea OAuth Client ID")
    oauth_client_secret: Optional[str] = Field(
        None, description="Gitea OAuth Client Secret"
    )
    oauth_redirect_url: Optional[str] = Field(
        None, description="OAuth回调地址，通常指向 /api/auth/callback"
    )
    oauth_scopes: list[str] | str = Field(
        default_factory=lambda: ["read:user", "read:repository"],
        description="OAuth申请的scope列表",
    )
    session_cookie_name: str = Field("gitea_session", description="会话Cookie名称")
    session_cookie_secure: bool = Field(
        False, description="是否仅通过HTTPS发送会话Cookie"
    )

    # 管理后台配置
    admin_enabled: bool = Field(True, description="是否启用管理后台")
    initial_admin_username: Optional[str] = Field(
        None, description="初始管理员用户名（首次启动时自动创建）"
    )
    webhook_log_retention_days: int = Field(30, description="Webhook日志保留天数")
    webhook_log_retention_days_failed: int = Field(
        90, description="失败的Webhook日志保留天数"
    )

    @field_validator("oauth_scopes", mode="after")
    @classmethod
    def _parse_scopes(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [scope.strip() for scope in value.split(",") if scope.strip()]
        return value

    # 可选：允许从不同环境文件加载
    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Settings":
        """
        构造一个Settings实例，允许覆盖默认的env文件路径。
        """
        if env_file:
            env_path = Path(env_file)
            if not env_path.is_absolute():
                env_path = (BASE_DIR / env_path).resolve()
            return cls(
                _env_file=str(env_path),
                _env_file_encoding="utf-8",
            )
        return cls()


# 全局配置实例
settings = Settings()

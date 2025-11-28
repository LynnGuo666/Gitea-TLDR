"""
配置管理模块
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""

    # Gitea配置
    gitea_url: str = Field(..., description="Gitea服务器URL")
    gitea_token: str = Field(..., description="Gitea访问令牌")

    # Webhook配置
    webhook_secret: Optional[str] = Field(None, description="Webhook密钥用于验证请求")

    # Claude Code配置
    claude_code_path: str = Field("claude", description="Claude Code CLI路径")

    # 工作目录配置
    work_dir: str = Field("/tmp/gitea-pr-reviewer", description="临时工作目录")

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
        description="默认审查重点"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 全局配置实例
settings = Settings()

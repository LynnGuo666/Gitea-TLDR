"""
版本信息模块
"""

__version__ = "1.5.1"
__release_date__ = "2025-12-15"
__author__ = "LynnGuo666"

# 版本历史
VERSION_HISTORY = {
    "1.5.1": {
        "date": "2025-12-15",
        "changes": [
            "优化：仓库列表API只返回用户有admin权限的仓库",
            "修复：添加greenlet依赖，修复SQLAlchemy异步引擎初始化失败问题"
        ]
    },
    "1.5.0": {
        "date": "2025-12-15",
        "changes": [
            "新增：仓库权限检查API，支持OAuth用户权限验证",
            "新增：GiteaClient.get_repository()方法，获取仓库详细信息",
            "新增：GiteaClient.check_repo_permissions()方法，检查用户权限",
            "新增：API端点 /api/repos/{owner}/{repo}/permissions",
            "优化：所有写操作的错误处理，区分权限错误和其他错误",
            "优化：权限不足时记录warning级别日志，便于排查问题"
        ]
    },
    "1.4.0": {
        "date": "2025-12-13",
        "changes": [
            "新增：SQLite数据库支持，使用SQLAlchemy ORM管理数据",
            "新增：审查历史记录，完整保存每次PR审查的详细信息",
            "新增：使用量统计，追踪API调用次数和token消耗估算",
            "新增：模型配置管理，支持全局和仓库级别的AI配置",
            "新增：API端点 /api/reviews、/api/stats、/api/configs、/api/repositories",
            "优化：仓库注册表支持数据库存储，自动从JSON迁移",
            "优化：Webhook处理器自动记录审查会话到数据库"
        ]
    },
    "1.3.0": {
        "date": "2025-12-09",
        "changes": [
            "新增：Claude输出结构化JSON，并可生成精确到文件/行的审查意见",
            "新增：自动向PR Review附加行级评论并携带对应commit id",
            "优化：审查状态根据整体严重程度自动标记"
        ]
    },
    "1.2.0": {
        "date": "2025-11-29",
        "changes": [
            "更新：最低 Python 版本要求提升至 3.11+，与依赖栈保持一致"
        ]
    },
    "1.1.0": {
        "date": "2025-11-28",
        "changes": [
            "新增：自动将bot设置为PR审查者",
            "新增：AUTO_REQUEST_REVIEWER配置项，控制是否自动请求审查者",
            "新增：GiteaClient.request_reviewer()方法，支持请求PR审查者",
            "优化：创建review后自动将bot添加到审查者列表",
        ]
    },
    "1.0.0": {
        "date": "2025-11-28",
        "changes": [
            "初始版本发布",
            "支持自动化PR审查（通过webhook）",
            "支持手动触发审查（通过评论命令 /review）",
            "支持Debug模式，详细日志输出",
            "支持多种审查功能：评论、审查、状态",
            "支持多维度审查：代码质量、安全、性能、逻辑",
            "使用Claude Code CLI进行代码分析",
            "完整代码库上下文分析",
            "模块化架构设计",
        ]
    }
}


def get_version_info() -> str:
    """
    获取版本信息字符串

    Returns:
        格式化的版本信息
    """
    return f"Gitea PR Reviewer v{__version__} ({__release_date__})"


def get_version_banner() -> str:
    """
    获取版本横幅（启动时显示）

    Returns:
        格式化的版本横幅
    """
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║             Gitea PR Reviewer v{__version__}                    ║
║                                                              ║
║  基于Claude Code的Gitea Pull Request自动审查工具             ║
║  Release Date: {__release_date__}                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    return banner


def get_changelog(version: str = None) -> str:
    """
    获取更新日志

    Args:
        version: 版本号，如果为None则返回当前版本的更新日志

    Returns:
        格式化的更新日志
    """
    target_version = version or __version__

    if target_version not in VERSION_HISTORY:
        return f"未找到版本 {target_version} 的更新日志"

    info = VERSION_HISTORY[target_version]
    changelog = f"\n版本 {target_version} ({info['date']})\n"
    changelog += "=" * 60 + "\n"
    for change in info["changes"]:
        changelog += f"  • {change}\n"

    return changelog


def get_all_changelogs() -> str:
    """
    获取所有版本的更新日志

    Returns:
        格式化的完整更新日志
    """
    all_logs = "\n更新日志\n" + "=" * 60 + "\n"

    # 按版本号倒序排列
    sorted_versions = sorted(VERSION_HISTORY.keys(), reverse=True)

    for version in sorted_versions:
        info = VERSION_HISTORY[version]
        all_logs += f"\n版本 {version} ({info['date']})\n"
        all_logs += "-" * 60 + "\n"
        for change in info["changes"]:
            all_logs += f"  • {change}\n"

    return all_logs

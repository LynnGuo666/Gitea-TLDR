"""
版本信息模块
"""

__version__ = "1.1.0"
__release_date__ = "2025-11-28"
__author__ = "Gitea-TLDR Team"

# 版本历史
VERSION_HISTORY = {
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

"""
版本信息模块
"""

__version__ = "1.15.0"
__release_date__ = "2026-02-14"
__author__ = "LynnGuo666"

# 版本历史
VERSION_HISTORY = {
    "1.15.0": {
        "date": "2026-02-14",
        "changes": [
            "新增：CodexProvider（OpenAI Codex CLI）审查引擎实现",
            "新增：CODEX_CLI_PATH / CODEX_API_KEY 配置项",
            "优化：ReviewEngine 支持多 CLI 路径动态选择",
        ],
    },
    "1.14.0": {
        "date": "2026-02-14",
        "changes": [
            "重构：引入 Provider/Adapter 模式，支持多审查引擎（Claude Code、Codex 等）",
            "新增：ReviewProvider 抽象基类、ClaudeCodeProvider 实现、ProviderRegistry 注册表",
            "新增：ReviewEngine 统一入口，根据配置路由到对应 Provider",
            "新增：API 端点 /api/config/provider-global 与 /api/repos/{owner}/{repo}/provider-config",
            "重构：数据库字段重命名 anthropic_* → provider_*，claude_api_calls → provider_api_calls",
            "优化：保留旧 API 端点与字段别名，确保向后兼容",
            "优化：前端 AI 审查配置 Tab 更新为 Provider 抽象命名",
        ],
    },
    "1.13.1": {
        "date": "2026-02-13",
        "changes": [
            "优化：移动端导航改为顶部标题栏 + 下拉菜单，避免侧边栏挤压页面",
            "优化：移动端导航下拉增加过渡动画并采用悬浮层显示，不再推动正文下移",
            "优化：增强导航玻璃层不透明度，提升可读性",
        ],
    },
    "1.13.0": {
        "date": "2026-02-13",
        "changes": [
            "优化：统一前端页面标题体系，新增 PageHeader 与 SectionHeader 组件",
            "优化：仓库配置页 Tab 内容移除重复分区标题，减少分割线干扰",
            "优化：仓库配置页改为顶部全局刷新，一次刷新 Webhook/Claude/PR 数据",
            "优化：仓库页与设置页内容宽度统一为 max-w-[1100px]，与主页保持一致",
        ],
    },
    "1.12.0": {
        "date": "2026-01-21",
        "changes": [
            "优化：仓库列表显示所有可访问仓库，无管理权限的仓库标记为只读",
            "优化：只读仓库不可点击进入详情页，只能查看列表",
            "优化：新增只读筛选器，支持筛选全部/可管理/只读仓库",
            "新增：仓库列表页面顶部显示只读仓库提示信息",
        ],
    },
    "1.10.0": {
        "date": "2026-01-21",
        "changes": [
            "优化：移除前端 API 降级使用 Bot PAT 的逻辑，所有前端操作必须 OAuth 登录",
            "优化：前端 UI 更新，移除默认 PAT 提示，改为提示配置 OAuth",
        ],
    },
    "1.9.1": {
        "date": "2026-01-21",
        "changes": [
            "优化：PR列表布局调整，状态徽章和箭头水平排列在同一行",
            "优化：移除仓库配置页面的服务信息卡片",
        ],
    },
    "1.9.0": {
        "date": "2026-01-21",
        "changes": [
            "新增：仓库配置页面显示最新Pull Requests替代提交历史",
            "新增：PR列表显示状态徽章（打开/已关闭/已合并）",
            "新增：PR列表显示分支信息（源分支→目标分支）",
            "新增：后端API端点 GET /api/repos/{owner}/{repo}/pulls 支持获取PR列表",
            "优化：前端UI改进，移除Radix UI依赖，使用原生HTML元素和自定义样式",
        ],
    },
    "1.8.1": {
        "date": "2026-01-21",
        "changes": [
            "修复：管理后台统计因UsageStat字段名不匹配导致的500错误",
            "修复：管理后台权限校验读取错误数据库上下文导致的异常",
            "优化：组织仓库配置权限，要求组织管理员才能修改Webhook与Claude配置",
        ],
    },
    "1.7.0": {
        "date": "2026-01-20",
        "changes": [
            "新增：仓库级别Anthropic配置，支持为每个仓库配置独立的API Base URL和Auth Token",
            "新增：Webhook Secret管理，支持查看和重新生成仓库的Webhook Secret",
            "新增：API端点 /api/repos/{owner}/{repo}/claude-config (GET/PUT)",
            "新增：API端点 /api/repos/{owner}/{repo}/webhook-secret (GET)",
            "新增：API端点 /api/repos/{owner}/{repo}/webhook-secret/regenerate (POST)",
            "优化：claude_analyzer支持传递自定义Anthropic配置到Claude Code CLI",
            "优化：webhook_handler自动读取仓库的Anthropic配置",
            "优化：前端仓库配置页面新增Claude配置表单",
        ],
    },
    "1.6.0": {
        "date": "2025-12-16",
        "changes": [
            "新增：前端暗色模式支持，可通过侧边栏按钮切换主题",
            "新增：CSS变量系统，统一设计规范",
            "新增：骨架屏加载动画，改善加载体验",
            "新增：Toast通知组件，操作反馈更直观",
            "新增：仓库搜索功能，支持实时筛选",
            "新增：Webhook状态API，自动检测仓库配置状态",
            "新增：Webhook删除API，支持禁用自动审查",
            "新增：Toggle开关组件，直观展示Webhook启用状态",
            "优化：auth轮询机制，窗口聚焦时自动刷新",
            "优化：移动端响应式布局",
            "优化：用量统计页面连接真实API",
        ],
    },
    "1.5.1": {
        "date": "2025-12-15",
        "changes": [
            "优化：仓库列表API只返回用户有admin权限的仓库",
            "修复：添加greenlet依赖，修复SQLAlchemy异步引擎初始化失败问题",
        ],
    },
    "1.5.0": {
        "date": "2025-12-15",
        "changes": [
            "新增：仓库权限检查API，支持OAuth用户权限验证",
            "新增：GiteaClient.get_repository()方法，获取仓库详细信息",
            "新增：GiteaClient.check_repo_permissions()方法，检查用户权限",
            "新增：API端点 /api/repos/{owner}/{repo}/permissions",
            "优化：所有写操作的错误处理，区分权限错误和其他错误",
            "优化：权限不足时记录warning级别日志，便于排查问题",
        ],
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
            "优化：Webhook处理器自动记录审查会话到数据库",
        ],
    },
    "1.3.0": {
        "date": "2025-12-09",
        "changes": [
            "新增：Claude输出结构化JSON，并可生成精确到文件/行的审查意见",
            "新增：自动向PR Review附加行级评论并携带对应commit id",
            "优化：审查状态根据整体严重程度自动标记",
        ],
    },
    "1.2.0": {
        "date": "2025-11-29",
        "changes": ["更新：最低 Python 版本要求提升至 3.11+，与依赖栈保持一致"],
    },
    "1.1.0": {
        "date": "2025-11-28",
        "changes": [
            "新增：自动将bot设置为PR审查者",
            "新增：AUTO_REQUEST_REVIEWER配置项，控制是否自动请求审查者",
            "新增：GiteaClient.request_reviewer()方法，支持请求PR审查者",
            "优化：创建review后自动将bot添加到审查者列表",
        ],
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
        ],
    },
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
║  基于多引擎的Gitea Pull Request自动审查工具             ║
║  Release Date: {__release_date__}                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    return banner


def get_changelog(version: str | None = None) -> str:
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

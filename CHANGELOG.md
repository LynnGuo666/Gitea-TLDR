# 更新日志 (CHANGELOG)

所有重要的项目变更都将记录在此文件中。

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)规范。

## [1.8.0] - 2026-01-20

### 新增功能 (Added)

- **管理后台系统**: 全新的管理后台功能，支持系统管理和监控
  - Dashboard 看板：实时统计审查次数、Token 消耗、Webhook 状态、仓库数量
  - 管理员用户管理：支持创建、更新、删除管理员，区分 super_admin 和 admin 角色
  - 全局配置管理：统一管理系统配置（Claude、审查、性能、高级选项）
  - Webhook 日志查看：完整记录所有 Webhook 请求，支持查看详情和重试
  - 权限控制：基于数据库的管理员列表，支持灵活的权限配置

### 数据库模型 (Database)

- `AdminUser`: 管理员用户表，支持角色（super_admin/admin）和权限配置
- `AdminSettings`: 全局配置表，分类存储系统配置（claude/review/performance/advanced）
- `ApiKey`: API Key 池表，支持多 Key 管理、配额监控、轮换策略
- `WebhookLog`: Webhook 日志表，记录所有请求的完整信息和处理状态

### API 端点 (Endpoints)

**管理后台 API** (需要管理员权限)
- `GET /api/admin/dashboard/stats`: 获取 Dashboard 统计数据
- `GET /api/admin/users`: 获取管理员列表
- `POST /api/admin/users`: 创建管理员用户
- `PUT /api/admin/users/{username}`: 更新管理员用户
- `DELETE /api/admin/users/{username}`: 删除管理员用户
- `GET /api/admin/settings`: 获取全局配置
- `PUT /api/admin/settings/{key}`: 更新配置项
- `DELETE /api/admin/settings/{key}`: 删除配置项
- `GET /api/admin/webhooks/logs`: 获取 Webhook 日志列表
- `GET /api/admin/webhooks/logs/{id}`: 获取日志详情

### 前端页面 (Frontend)

- `/admin`: 管理后台 Dashboard，展示系统统计和快捷操作
- 侧边栏新增"管理后台"入口（登录后可见）
- 新增管理后台专用图标（AdminIcon, ChartIcon, LogIcon）

### 配置选项 (Configuration)

新增环境变量：
- `ADMIN_ENABLED=true`: 是否启用管理后台（默认启用）
- `INITIAL_ADMIN_USERNAME=admin`: 初始管理员用户名（首次启动自动创建）
- `WEBHOOK_LOG_RETENTION_DAYS=30`: Webhook 日志保留天数
- `WEBHOOK_LOG_RETENTION_DAYS_FAILED=90`: 失败日志保留天数

### 技术改进 (Technical)

- **权限中间件**: 实现 `admin_auth.py`，提供 `admin_required()` 装饰器用于权限控制
- **管理服务**: `AdminService` 封装所有管理后台相关的数据库操作
- **初始化流程**: 应用启动时自动创建初始管理员用户
- **日志清理**: 支持自动清理旧的 Webhook 日志（区分成功/失败日志保留时间）

### 使用说明 (Usage)

1. 在 `.env` 中配置 `INITIAL_ADMIN_USERNAME=your_username`
2. 启动应用后，使用配置的用户名登录
3. 访问 `/admin` 即可进入管理后台
4. super_admin 可以创建其他管理员，admin 只能管理自己的信息

## [1.7.0] - 2026-01-20

### 新增功能 (Added)

- **仓库级别 Anthropic 配置**: 支持为每个仓库配置独立的 API Base URL 和 Auth Token，实现灵活的 API 配置管理
- **Webhook Secret 管理**: 新增查看和重新生成 Webhook Secret 的功能，提升安全性

### API端点 (Endpoints)

- `GET /api/repos/{owner}/{repo}/claude-config`: 获取仓库的 Claude 配置（Base URL 和 Token 状态）
- `PUT /api/repos/{owner}/{repo}/claude-config`: 保存或更新仓库的 Claude 配置
- `GET /api/repos/{owner}/{repo}/webhook-secret`: 获取仓库的 Webhook Secret
- `POST /api/repos/{owner}/{repo}/webhook-secret/regenerate`: 重新生成 Webhook Secret

### 技术改进 (Technical)

- **claude_analyzer 增强**: `analyze_pr()` 和 `analyze_pr_simple()` 方法支持传递自定义 `anthropic_base_url` 和 `anthropic_auth_token` 参数
- **webhook_handler 优化**: 自动从数据库读取仓库的 Anthropic 配置并传递给 Claude Code CLI
- **前端配置页面**: 仓库配置页面新增 Claude 配置表单，支持输入和保存 Base URL 和 API Key

### 数据库模型 (Database)

- `ModelConfig` 模型新增字段：`anthropic_base_url` (String 500)、`anthropic_auth_token` (String 500)

### 使用场景 (Use Cases)

- 为不同仓库使用不同的 Anthropic API 端点（如代理或私有部署）
- 为不同团队配置独立的 API Token，实现成本隔离和配额管理
- 敏感仓库使用专用 API 配置，提升安全性

## [1.6.0] - 2025-12-16

### 新增功能 (Added)

- **暗色模式**: 前端支持亮色/暗色主题切换，可通过侧边栏按钮切换，偏好自动保存到本地
- **CSS变量系统**: 引入完整的CSS变量体系，统一颜色、间距、圆角、阴影等设计规范
- **骨架屏加载**: 新增Skeleton组件，仓库列表和卡片加载时显示平滑的骨架屏动画
- **Toast通知**: 新增Toast组件，支持success/error/warning/info四种类型，操作反馈更直观
- **仓库搜索**: 首页新增搜索框，支持按仓库名称实时筛选（仓库数超过3个时显示）
- **刷新按钮**: 仓库列表和用量统计页面新增手动刷新按钮，带旋转动画
- **Webhook状态检测**: 仓库配置页面自动检测Webhook是否已配置
- **Toggle开关**: 新增Toggle Switch组件，直观展示和控制Webhook启用状态

### API端点 (Endpoints)

- `GET /api/repos/{owner}/{repo}/webhook-status`: 获取仓库Webhook配置状态，返回是否已配置、是否激活、监听事件列表
- `DELETE /api/repos/{owner}/{repo}/webhook`: 删除仓库的Webhook配置

### 技术改进 (Technical)

- **自定义Hooks**: 新增 `useLocalStorage`、`useTheme`、`useDebounce`、`useWindowFocus` 等React Hooks
- **智能轮询**: auth状态轮询从5秒改为10-30秒，窗口聚焦时自动刷新，降低不必要的请求
- **响应式优化**: 改进移动端布局，侧边栏在小屏幕上显示为顶部导航
- **用量统计**: 用量页面从硬编码数据改为连接真实 `/api/stats` API
- **组件库**: 新增 `components/ui/` 目录，包含Skeleton、Toast等通用组件

### 前端文件结构 (Frontend Structure)

- `lib/hooks.ts`: 自定义React Hooks
- `components/ui/Skeleton.tsx`: 骨架屏组件
- `components/ui/Toast.tsx`: Toast通知组件
- `components/ui/index.ts`: 组件导出
- `components/icons.tsx`: 新增SunIcon、MoonIcon、SearchIcon、RefreshIcon图标

## [1.5.1] - 2025-12-15

### 优化 (Improved)

- **仓库列表过滤**: `/api/repos` 接口只返回用户有admin权限的仓库，因为只有admin才能配置webhook

### 问题修复 (Fixed)

- **数据库初始化**: 添加greenlet依赖，修复SQLAlchemy异步引擎初始化时报错 "the greenlet library is required"

## [1.5.0] - 2025-12-15

### 新增功能 (Added)

- **权限检查API**: 新增仓库权限检查功能，支持OAuth用户权限验证
- **仓库信息获取**: 新增 `GiteaClient.get_repository()` 方法，获取仓库详细信息（包含权限）
- **权限验证方法**: 新增 `GiteaClient.check_repo_permissions()` 方法，检查用户对仓库的admin/push/pull权限

### API端点 (Endpoints)

- `GET /api/repos/{owner}/{repo}/permissions`: 检查当前用户对指定仓库的权限，返回权限详情和是否可设置webhook

### 技术改进 (Technical)

- 优化所有写操作的错误处理，区分权限错误（401/403）和其他错误
- 权限不足时记录warning级别日志，便于排查问题
- 改进以下方法的错误处理：
  - `create_issue_comment()`: 创建PR评论
  - `update_issue_comment()`: 更新PR评论
  - `create_review()`: 创建PR审查
  - `create_commit_status()`: 设置提交状态
  - `request_reviewer()`: 请求审查者
  - `add_collaborator()`: 邀请协作者

### 使用场景 (Use Cases)

- OAuth用户登录后，前端可通过权限API判断是否显示webhook设置按钮
- 只有具有admin权限的用户才能看到仓库管理功能
- 权限不足时，系统会优雅降级，记录警告日志而不是错误

## [1.4.0] - 2025-12-13

### 新增功能 (Added)

- **数据库支持**: 新增SQLite数据库，使用SQLAlchemy ORM管理所有数据
- **审查历史**: 完整记录每次PR审查的详细信息，包括触发类型、分析模式、审查结果
- **行级评论存储**: 保存Claude返回的所有行级评论，支持后续查询和分析
- **使用量统计**: 追踪API调用次数、token消耗估算、克隆操作次数
- **模型配置管理**: 支持全局和仓库级别的AI模型配置

### API端点 (Endpoints)

- `GET /api/reviews`: 获取审查历史列表，支持按仓库筛选和分页
- `GET /api/reviews/{id}`: 获取审查详情，包含行级评论
- `GET /api/stats`: 获取使用量统计汇总和详情
- `GET /api/configs`: 获取所有模型配置
- `POST /api/configs`: 创建或更新模型配置
- `GET /api/repositories`: 获取所有已配置的仓库

### 技术改进 (Technical)

- 新增 `app/core/database.py`: 异步数据库连接管理
- 新增 `app/models/`: ORM模型目录，包含5个数据表模型
- 新增 `app/services/db_service.py`: 数据库操作服务层
- 仓库注册表支持数据库存储，启动时自动从JSON迁移
- Webhook处理器自动记录审查会话和使用量到数据库

### 数据库表结构 (Database Schema)

- `repositories`: 仓库基础信息和webhook密钥
- `model_configs`: AI模型配置（全局/仓库级别）
- `review_sessions`: 审查会话记录
- `inline_comments`: 行级评论详情
- `usage_stats`: 使用量统计

### 配置选项 (Configuration)

- `DATABASE_URL`: 数据库连接URL（可选，默认使用工作目录下的SQLite文件）

## [1.3.0] - 2025-12-09

### 新增功能 (Added)

- **行级审查**: Claude 现在会返回结构化 JSON，机器人可在 PR Review 中针对具体文件与行号留下评论，审查结果也会同步到总览评论中
- **审查增强**: 自动/手动触发均复用同一审查流程，行级评论与整体报告可同时输出

### 技术改进 (Technical)

- Claude 提示词强制 JSON 输出，解析逻辑可从回复中提取 `summary_markdown`、严重程度与行级建议
- Gitea Client 在创建 Review 时携带 `commit_id`，并根据分析结果动态设置提交状态

## [1.2.0] - 2025-11-29

### 新增 (Added)

- `AGENTS.md`：新增贡献者/agent 指南，说明项目结构、开发命令、提交流程与版本同步规范
- 前端：头像 + 用户下拉菜单组件，提升仪表盘可用性
- OAuth：新增登录入口与配置说明，前端 UI 同步展示登录状态

### 改进 (Improved)

- API 路由拆分为公共与私有两组，前端仪表盘布局随之调整，仓库列表交互体验优化
- 启动日志输出 `Debug模式: 开启/关闭`，首屏即可确认运行模式
- README 运行要求更新为 **Python 3.11+**，并同步记录在 `app/core/version.py`

### 修复 (Fixed)

- `python app/main.py` 运行方式改为使用 `app.main:app` import string，解决 Uvicorn 在 debug 模式下的 reload 警告
- 更新依赖与样式资源，避免旧版前端包导致的布局混乱

## [1.1.0] - 2025-11-28

### 新增功能 (Added)

- **自动审查者设置**: 创建PR review后自动将bot添加到审查者列表
- **审查者API**: 新增 `GiteaClient.request_reviewer()` 方法，支持通过API请求PR审查者
- **配置选项**: 新增 `AUTO_REQUEST_REVIEWER` 环境变量，控制是否自动请求审查者（默认为true）

### 技术改进 (Technical)

- 在 `webhook_handler.py` 中集成自动请求审查者逻辑
- 只有当review创建成功且配置了bot用户名时才会自动请求审查者
- 支持自动触发和手动触发两种场景

### 配置选项 (Configuration)

- `AUTO_REQUEST_REVIEWER`: 是否自动将bot设置为审查者（默认: true）
- `BOT_USERNAME`: Bot用户名，自动请求审查者时必需

## [1.0.0] - 2025-11-28

### 新增功能 (Added)

- **自动化审查**: 支持通过Gitea Webhook自动触发PR代码审查
- **手动触发**: 支持在PR评论中使用 `/review` 命令手动触发审查
- **完整上下文分析**: 克隆完整代码库，提供完整上下文给Claude Code进行分析
- **多种反馈机制**: 支持PR评论（Comment）、PR审查（Review）、提交状态（Status）三种反馈方式
- **多维度审查**: 支持代码质量、安全漏洞、性能问题、逻辑错误四个维度的审查
- **Debug模式**: 支持详细日志输出，包括所有API请求/响应、Webhook payload、Claude提示词和响应
- **命令解析器**: 模块化的命令解析系统，支持 `--features` 和 `--focus` 参数
- **版本管理系统**: 完整的版本号和更新日志管理

### 技术特性 (Technical)

- **模块化架构**: 清晰的模块划分，便于维护和扩展
  - `main.py`: FastAPI应用入口
  - `config.py`: 配置管理
  - `gitea_client.py`: Gitea API客户端，支持debug日志
  - `repo_manager.py`: 代码库克隆和管理
  - `claude_analyzer.py`: Claude Code CLI调用
  - `webhook_handler.py`: Webhook处理逻辑
  - `command_parser.py`: 命令解析器
  - `version.py`: 版本信息管理

- **异步处理**: 使用FastAPI异步框架，webhook立即返回202，后台处理审查任务
- **安全验证**: 支持Webhook签名验证
- **灵活配置**:
  - 支持环境变量配置
  - 支持HTTP标头配置（自动触发）
  - 支持命令参数配置（手动触发）

### 配置选项 (Configuration)

- `GITEA_URL`: Gitea服务器地址
- `GITEA_TOKEN`: Gitea访问令牌
- `WEBHOOK_SECRET`: Webhook密钥（可选）
- `CLAUDE_CODE_PATH`: Claude Code CLI路径
- `WORK_DIR`: 临时工作目录
- `HOST` / `PORT`: 服务器配置
- `LOG_LEVEL`: 日志级别
- `DEBUG`: Debug模式开关
- `BOT_USERNAME`: Bot用户名（用于手动触发，可选）

### 使用示例 (Examples)

#### 自动触发
当PR被创建或更新时，自动触发审查。

#### 手动触发
```
# 基本用法
/review

# 带@提及
@pr-reviewer-bot /review

# 指定功能和重点
@pr-reviewer-bot /review --features comment,status --focus security,performance
```

### Claude Code集成 (Claude Integration)

- 使用 `-p` 参数传递提示词
- 通过stdin传递diff内容
- 支持完整代码库上下文
- 支持简单模式（仅diff分析）作为降级方案

### API端点 (Endpoints)

- `GET /`: 健康检查，返回版本信息
- `GET /health`: 健康检查
- `POST /webhook`: Webhook接收端点
  - 支持 `pull_request` 事件（自动触发）
  - 支持 `issue_comment` 事件（手动触发）

### 工作流程 (Workflow)

1. 接收webhook或命令
2. 验证签名/解析命令
3. 返回202，启动后台任务
4. 获取PR diff
5. 克隆代码库
6. 调用Claude Code分析
7. 发布审查结果（评论/审查/状态）
8. 清理临时文件

---

## 版本规范说明

- **主版本号（Major）**: 不兼容的API修改
- **次版本号（Minor）**: 向下兼容的功能性新增
- **修订号（Patch）**: 向下兼容的问题修正

## 更新类型说明

- `Added`: 新增功能
- `Changed`: 功能变更
- `Deprecated`: 即将废弃的功能
- `Removed`: 已移除的功能
- `Fixed`: 问题修复
- `Security`: 安全相关

---

**注**: 未来版本的更新日志将在此文件顶部按时间倒序添加。

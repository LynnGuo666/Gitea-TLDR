# 更新日志 (CHANGELOG)

所有重要的项目变更都将记录在此文件中。

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)规范。

## [1.19.4] - 2026-02-15

### 新增功能 (Added)

- **仓库审查功能开关**: 仓库配置页“审查方向”新增 `comment/review/status` 功能开关，支持直接保存到 `default_features`

### 优化 (Improved)

- **配置可读性**: 审查配置页拆分“审查功能”和“审查重点”展示，并增加启用数量提示
- **版本一致性**: 同步更新后端与前端版本号到 `1.19.4`

## [1.19.3] - 2026-02-15

### 新增功能 (Added)

- **全局配置管理页面落地**: `/admin/config` 接入 `GET/PUT/DELETE /api/admin/settings`，支持配置列表展示、分类过滤、JSON 编辑与删除
- **仓库管理页面完善**: `/admin/repos` 接入 `GET /api/repositories`，支持状态统计、关键词过滤与仓库详情跳转
- **Webhook 日志页面完善**: `/admin/webhooks` 接入 `GET /api/admin/webhooks/logs` 与详情接口，支持状态筛选、分页和展开查看 payload

### 优化 (Improved)

- **管理后台布局统一**: 管理后台首页及管理子页面移除 Card 容器，统一为 `PageHeader + 分区边框` 结构，和现有页面规范保持一致
- **权限反馈体验**: 管理后台首页在权限不足时改为页面内提示，不再静默跳转
- **版本一致性**: 同步更新后端与前端版本号到 `1.19.3`

## [1.19.2] - 2026-02-15

### 新增功能 (Added)

- **管理员状态接口**: 新增 `GET /api/auth/admin-status`，用于返回当前会话的管理后台可访问状态（`enabled`/`logged_in`/`is_admin`/`role`）

### 优化 (Improved)

- **管理后台入口展示逻辑**: 侧边栏“管理后台”标签改为根据管理员状态显示，非管理员用户登录后不再看到入口
- **版本一致性**: 同步更新后端与前端版本号到 `1.19.2`

## [1.19.1] - 2026-02-15

### 修复 (Fixed)

- **模型字段语义修复**: 修复审查会话落库链路中 `model` 被错误写成 provider 名（`codex_cli` / `claude_code`）的问题，统一记录真实模型标识
- **Codex 默认模型更新**: `CodexProvider` 默认模型升级为 `gpt-5.3-codex`，并将最终解析模型写入 `usage_metadata` 供审查记录持久化
- **API 字段一致性**: Provider 配置与 Model 配置相关接口统一返回并支持保存 `engine` + `model`，避免 `model` 字段误映射为 `engine`

### 优化 (Improved)

- **前端配置体验**: 个人设置与仓库设置新增可选 `Model ID` 输入，支持按 provider 显式配置目标模型
- **审查记录展示一致性**: 审查列表/详情页面统一区分展示引擎与模型，避免在“模型”位置回退显示 provider 名
- **版本一致性**: 同步更新后端与前端版本号到 `1.19.1`

## [1.19.0] - 2026-02-15

### 重构 (Refactored)

- **数据库字段全面重命名**: `model_configs` 表字段 `model_name→engine`、`provider_api_base_url→api_url`、`provider_auth_token→api_key`，消除"模型名"与"引擎名"的命名歧义
- **审查记录字段重命名**: `review_sessions` 表字段 `provider_name→engine`、`model_name→model`
- **API 响应字段统一简化**: 移除冗余的 `anthropic_base_url`、`provider_has_auth_token`，统一为 `engine`/`model`/`api_url`/`has_api_key`
- **前端类型与字段全量同步**: 所有 TypeScript 类型定义和 API 调用点适配新字段名

### 新增功能 (Added)

- **model 字段**: `model_configs` 新增 `model` 列，用于存储实际调用的 LLM 模型标识（如 `gpt-5.2-codex`），与 `engine`（引擎标识）彻底分离

### 优化 (Improved)

- **版本一致性**: 同步更新后端与前端版本号到 `1.19.0`

## [1.18.4] - 2026-02-15

### 新增功能 (Added)

- **Codex wire_api 配置透传**: `model_configs` 新增 `wire_api` 字段，支持按配置在 `responses` 与 `chat-completions` 间切换，并贯穿 webhook 到 provider 调用链路

### 重构 (Refactored)

- **Codex CLI 调用模型**: `CodexProvider` 改为每次调用动态生成隔离的 `CODEX_HOME/config.toml`，通过 `model_provider + model + wire_api + env_key` 驱动 `codex exec`
- **环境隔离**: 子进程环境由全量继承改为最小化传递（`CODEX_HOME`/`CODEX_API_KEY`/`PATH`/`HOME`），避免宿主 `OPENAI_*` 配置污染

### 优化 (Improved)

- **版本一致性**: 同步更新后端与前端版本号到 `1.18.4`

## [1.18.3] - 2026-02-14

### 新增功能 (Added)

- **审查方向可视化**: 审查记录详情新增“审查方向”展示，按标签显示 `focus_areas`

### 优化 (Improved)

- **详情信息精简**: 审查记录详情移除分支信息展示（如 `main ← feature/...`）
- **版本一致性**: 同步更新后端与前端版本号到 `1.18.3`

## [1.18.2] - 2026-02-14

### 修复 (Fixed)

- **Alembic 多头冲突**: 移除重复迁移分支，恢复 `alembic upgrade head` 的单链路执行
- **我的审查接口崩溃**: 补齐 `ReviewSession` 的 `model_name`、`config_source` 字段映射，修复 `/api/my/reviews` 的属性访问异常
- **审查列表查询兼容性**: `DBService` 增加按仓库 ID 集合查询的方法，修复 `list_my_reviews` 调用缺失方法报错

### 优化 (Improved)

- **版本一致性**: 同步更新后端与前端版本号到 `1.18.2`

## [1.18.1] - 2026-02-14

### 修复 (Fixed)

- **Codex CLI 输入方式稳定性**: `codex exec` 改为通过 stdin 传递 prompt，避免超长命令参数和转义边界问题

### 优化 (Improved)

- **Codex CLI 输出读取稳定性**: 增加 `--output-last-message` 作为最终消息来源，减少 stdout 日志噪声对结果解析的干扰
- **版本一致性**: 同步更新后端与前端版本号到 `1.18.1`

## [1.18.0] - 2026-02-14

### 新增功能 (Added)

- **审查失败原因落库与透出**: 失败时记录 provider 执行错误（stderr/stdout/异常摘要），并通过审查历史接口返回
- **审查引擎可见性**: 审查会话新增 `provider_name` 字段，管理页审查历史可直接看到本次使用的引擎

### 优化 (Improved)

- **审查历史信息完整性**: 列表页补充“审查方向”与“失败原因”展示，展开详情移除 `main <- feature` 分支信息，仅保留必要的 Commit 信息
- **审查方向落库时机修复**: 调整审查会话创建顺序，先解析并确定 focus/features 再持久化，避免方向显示为空

## [1.13.0] - 2026-02-13

### 优化 (Improved)

- **页面标题体系统一**: 新增 `PageHeader` 与 `SectionHeader` 组件，统一页面主标题与分区标题语义和样式
  - 页面主标题统一为 `h1` 语义，分区标题统一为 `h2` 语义
  - 管理后台、仓库详情、设置页、用量页等页面统一接入标题组件

- **仓库详情页结构简化**: Tab 内容区移除重复标题，减少无意义分割线，信息层级更清晰

- **刷新交互统一**: 仓库详情页改为顶部单一全局刷新按钮
  - 一次操作并行刷新 Webhook 状态、Claude 配置与 PR 列表
  - 移除各 Tab 内部的局部刷新按钮，避免重复入口

- **页面宽度一致性**: 仓库详情页与设置页容器宽度统一为 `max-w-[1100px]`，与主页保持一致

## [1.12.0] - 2026-01-21

### 优化 (Improved)

- **仓库列表权限改进**: 现在所有可访问的仓库都会显示在列表中，无管理权限的仓库标记为只读
  - 仓库列表 API 返回所有可访问仓库，而非仅 admin 权限仓库
  - 只读仓库显示"只读"标签，使用普通 div 替代链接，不可点击进入详情页
  - 可管理仓库保持可点击状态

### 新增功能 (Added)

- **只读筛选器**: 仓库列表右上角新增权限筛选下拉菜单
  - "全部权限"：显示所有仓库
  - "可管理"：仅显示有管理权限的仓库
  - "只读"：仅显示无管理权限的仓库

- **只读提示信息**: 当列表中存在只读仓库时，顶部显示提示信息
  - 提示用户只读仓库无法配置 Webhook 和 Claude 设置
  - 使用锁定图标增强视觉提示

### 技术改进 (Technical)

- 前端 `RepoList` 组件改进：
  - 使用条件渲染 `ItemWrapper`（Link 或 div）控制点击行为
  - 只读仓库移除右侧箭头图标
  - 光标样式区分可点击/不可点击状态

## [1.11.0] - 2026-01-21

### 修复 (Fixed)

- **Toggle 开关显示**: 修复了 Webhook 启用状态下开关按钮显示错误的问题
  - 滑块被挤压或位置不正确
  - 改用 `left` 属性替代 `transform: translateX()` 控制位置
  - 使用 `top: 50%` + `translateY(-50%)` 实现垂直居中
  - 滑块使用纯白色 `#ffffff`，在绿色背景上更清晰

- **仓库启用状态逻辑**: 修复了首页所有仓库默认显示为"已启用"的问题
  - 后端 API：数据库无记录时，`is_active` 默认值从 `True` 改为 `False`
  - 前端：`repo.is_active` 空值合并默认值从 `true` 改为 `false`
  - 现在正确反映实际的 Webhook 配置状态

- **布局问题**: 修复了监听事件文本过长导致开关按钮被挤出容器的问题
  - Webhook 状态卡片添加 `gap` 间距
  - 文本区域使用 `flex: 1` 和 `min-width: 0` 自适应宽度
  - 开关添加 `flex-shrink: 0` 保持固定宽度
  - 长文本支持 `word-break: break-word` 自动换行

### 技术改进 (Technical)

- 优化 Toggle 开关 CSS，提升视觉一致性和可靠性
- 改进 Flexbox 布局，防止内容溢出和挤压

## [1.10.0] - 2026-01-21

### 优化 (Improved)

- **认证架构优化**: 前端所有 API 操作现在都必须通过 OAuth 登录，移除了降级使用 Bot PAT 的逻辑
  - Bot PAT (`GITEA_TOKEN`) 仅用于 webhook 处理时发送评论
  - 用户登录后使用自己的 OAuth token 管理仓库和配置 webhook
  - 提升了系统安全性，避免后端 Bot Token 被前端滥用

### 前端改进 (Frontend)

- 侧边栏底部提示更新：`"使用默认 PAT"` → `"请配置 OAuth 登录"`
- 新增 OAuth 未配置时的提示页面，提示管理员配置 OAuth
- 移除前端对 Bot PAT 的依赖

### 技术改进 (Technical)

- 以下 API 端点移除了降级逻辑，必须 OAuth 登录：
  - `GET /api/repos` - 列出仓库
  - `GET /api/repos/{owner}/{repo}/permissions` - 检查权限
  - `POST /api/repos/{owner}/{repo}/setup` - 配置 webhook
  - `GET /api/repos/{owner}/{repo}/webhook-status` - webhook 状态
  - `DELETE /api/repos/{owner}/{repo}/webhook` - 删除 webhook
  - `PUT /api/repos/{owner}/{repo}/claude-config` - Claude 配置
  - `POST /api/repos/{owner}/{repo}/webhook-secret/regenerate` - 重新生成 secret

## [1.9.1] - 2026-01-21

### 优化 (Improved)

- **PR 列表布局优化**: 调整 PR 卡片布局，状态徽章和箭头图标水平排列在同一行，中间留有合适间距
- **界面简化**: 移除仓库配置页面底部的"服务信息"卡片，简化页面结构

### 技术改进 (Technical)

- `.pr-status-row` 样式调整为水平布局（`flex-direction: row`）
- 状态徽章和箭头间距使用 `var(--spacing-md)` 保持一致性

## [1.9.0] - 2026-01-21

### 新增功能 (Added)

- **Pull Request 展示**: 仓库配置页面新增"最新 Pull Requests"卡片，替代原有的提交历史
  - 显示 PR 编号、标题、作者头像和用户名
  - 状态徽章：打开（绿色）、已关闭（红色）、已合并（紫色）
  - 分支信息：显示源分支 → 目标分支
  - 时间显示：相对时间（刚刚、X 分钟前、X 小时前、X 天前）
  - 刷新按钮：支持手动刷新 PR 列表
  - 外链跳转：点击 PR 卡片跳转到 Gitea PR 页面

### API端点 (Endpoints)

- `GET /api/repos/{owner}/{repo}/pulls`: 获取仓库的 Pull Request 列表
  - 参数：`state`（all/open/closed，默认 all）、`limit`（数量限制，默认 5）
  - 返回：PR 列表，包含编号、标题、状态、分支、作者、时间等信息

### 前端改进 (Frontend)

- 仓库配置页面 (`/repo/[owner]/[repo]`) 改进：
  - 新增 `.pr-list`、`.pr-item` 等 CSS 类，完整的 PR 卡片样式
  - PR 状态徽章样式：`.pr-status-open`、`.pr-status-closed`、`.pr-status-merged`
  - 移除"服务信息"卡片，简化页面布局
  - 移除 Radix UI Select 组件依赖，使用原生 HTML `<select>` 元素
  - 重写 RepoList 组件，移除 Radix UI Table 和 Badge 组件，使用卡片式布局

### 技术改进 (Technical)

- **后端**: `GiteaClient.list_pull_requests()` 方法，调用 Gitea API 获取 PR 列表
- **前端**: TypeScript 类型定义 `PullRequest`，包含所有必要字段
- **样式**: 新增 PR 专用 CSS 样式，与现有设计系统保持一致
- **性能**: 减少前端 bundle 大小（从 129 kB → 93.4 kB）

## [1.8.1] - 2026-01-21

### 修复 (Fixed)

- 修复管理后台统计因 UsageStat 字段名不匹配导致的 500 错误
- 修复管理后台权限校验读取错误数据库上下文导致的异常
- 优化组织仓库配置权限，要求组织管理员才能修改 Webhook 与 Claude 配置

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

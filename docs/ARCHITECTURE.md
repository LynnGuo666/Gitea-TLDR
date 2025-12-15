# Gitea PR Reviewer 架构文档

> **适用版本**: v1.5.1
> **文档日期**: 2025-12-15
> **注意**: 本文档描述的架构适用于 v1.4.0+ 版本（引入数据库系统后）

---

## 目录

1. [配置系统](#1-配置系统)
2. [数据库系统架构](#2-数据库系统架构)
3. [用户系统与认证](#3-用户系统与认证)
4. [整体调用流程](#4-整体调用流程)
5. [API 端点](#5-api-端点)
6. [数据流示例](#6-数据流示例)
7. [配置优先级](#7-配置优先级)

---

## 1. 配置系统

### 配置层级

```
.env 文件
  ↓
Settings (Pydantic BaseSettings)
  ↓
全局单例 settings 实例
  ↓
各服务组件使用 settings
```

**配置文件位置**: `app/core/config.py`

### 配置项分类

#### Gitea集成配置
| 变量 | 必需 | 说明 |
|------|------|------|
| `GITEA_URL` | 是 | Gitea服务器地址 |
| `GITEA_TOKEN` | 是 | API访问令牌 |

#### 数据库配置
| 变量 | 必需 | 说明 |
|------|------|------|
| `DATABASE_URL` | 否 | 自定义数据库连接URL，默认: `{WORK_DIR}/gitea_pr_reviewer.db` |

支持 MySQL, PostgreSQL 等任何 SQLAlchemy 支持的数据库。

#### Webhook配置
| 变量 | 必需 | 说明 |
|------|------|------|
| `WEBHOOK_SECRET` | 否 | HMAC签名验证密钥 |

#### Claude集成配置
| 变量 | 必需 | 说明 |
|------|------|------|
| `CLAUDE_CODE_PATH` | 否 | Claude CLI可执行文件路径，默认: `claude` |
| `ANTHROPIC_AUTH_TOKEN` | 否 | Claude认证令牌 |

#### 服务器配置
| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `HOST` | 否 | `0.0.0.0` | 监听地址 |
| `PORT` | 否 | `8000` | 监听端口 |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 |
| `DEBUG` | 否 | `false` | Debug模式 |

#### OAuth配置（可选）
| 变量 | 必需 | 说明 |
|------|------|------|
| `OAUTH_CLIENT_ID` | 否 | Gitea OAuth Client ID |
| `OAUTH_CLIENT_SECRET` | 否 | Gitea OAuth Client Secret |
| `OAUTH_REDIRECT_URL` | 否 | OAuth回调地址 |
| `OAUTH_SCOPES` | 否 | 申请的权限范围（逗号分隔） |

#### Bot配置
| 变量 | 必需 | 说明 |
|------|------|------|
| `BOT_USERNAME` | 否 | Bot用户名（用于识别评论中的@提及） |

#### 审查配置
| 变量 | 必需 | 说明 |
|------|------|------|
| `DEFAULT_REVIEW_FOCUS` | 否 | 默认审查重点 |
| `AUTO_REQUEST_REVIEWER` | 否 | 是否自动设置bot为审查者 |

---

## 2. 数据库系统架构

### 数据库初始化流程

```
FastAPI 启动
  ↓
main.py: create_app()
  ↓
lifespan() 生命周期事件触发
  ↓
Database.init() 初始化引擎
  ↓
Database.create_tables() 创建所有表
  ↓
尝试从JSON迁移数据到数据库
  ↓
更新 AppContext 中的数据库引用
```

**数据库管理类**: `app/core/database.py`

### 数据库特性

- **异步ORM**: 使用 SQLAlchemy 2.0 async/await
- **自动连接管理**: 使用上下文管理器自动提交/回滚
- **SQLite优化**:
  - 单线程模式禁用 (`check_same_thread=False`)
  - 静态连接池 (`StaticPool`)
  - 自动创建父目录
- **敏感信息隐藏**: 日志中隐藏密码

### ORM模型

**位置**: `app/models/`

#### 数据模型关系图

```
┌─────────────┐
│ Repository  │
└─────┬───────┘
      │
      ├──────────────────┬──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ ModelConfig │   │ReviewSession│   │  UsageStat  │
└─────────────┘   └──────┬──────┘   └─────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │InlineComment│
                  └─────────────┘
```

#### 1. Repository（仓库表）
```python
id (PK)
owner (String, 唯一约束)
repo_name (String, 唯一约束)
webhook_secret (可选)
is_active (Boolean)
created_at, updated_at (时间戳)

关系: model_config (1:1), review_sessions (1:N)
```

#### 2. ReviewSession（审查会话表）
```python
id (PK)
repository_id (FK)
pr_number, pr_title, pr_author
head_branch, base_branch, head_sha
trigger_type: "auto" | "manual"
enabled_features: JSON ["comment", "review", "status"]
focus_areas: JSON ["quality", "security", "performance", "logic"]
analysis_mode: "full" | "simple"
diff_size_bytes
overall_severity: "critical" | "high" | "medium" | "low" | "info"
summary_markdown
inline_comments_count
overall_success (Boolean)
error_message
started_at, completed_at, duration_seconds

关系: repository (N:1), inline_comments (1:N), usage_stat (1:1)
```

#### 3. ModelConfig（AI模型配置表）
```python
id (PK)
repository_id (FK, 可选 - NULL表示全局配置)
config_name, model_name ("claude")
max_tokens, temperature (可选)
custom_prompt (可选)
default_features: JSON
default_focus: JSON
is_default (Boolean)
created_at, updated_at

关系: repository (N:1)
```

#### 4. InlineComment（行级评论表）
```python
id (PK)
review_session_id (FK)
file_path, new_line, old_line
severity: "critical" | "high" | "medium" | "low"
comment, suggestion
created_at

关系: review_session (N:1)
```

#### 5. UsageStat（使用量统计表）
```python
id (PK)
repository_id (FK)
review_session_id (FK, 可选)
stat_date (Date)
estimated_input_tokens, estimated_output_tokens
gitea_api_calls, claude_api_calls, clone_operations
created_at

关系: repository (N:1), review_session (1:1)
```

### 数据库服务类

**位置**: `app/services/db_service.py`

提供统一的数据库操作接口：
- Repository CRUD + 列表
- ModelConfig 创建/查询/列表（支持全局和仓库级别）
- ReviewSession 创建/更新/查询（支持关联仓库过滤）
- InlineComment 保存和查询
- UsageStat 记录和统计汇总

**使用方式**：
```python
async with database.session() as session:
    db_service = DBService(session)
    repo = await db_service.get_or_create_repository(owner, repo_name)
    # ... 操作数据
    # 自动提交或回滚
```

---

## 3. 用户系统与认证

### OAuth登录流程

**位置**: `app/services/auth_manager.py`

```
前端: GET /api/auth/login-url
      ↓
AuthManager.build_authorize_url()
      ↓ (302) 重定向到
Gitea OAuth 授权页面
      ↓
用户授权后，Gitea回调
      ↓
前端: GET /api/auth/callback?code=XXX&state=YYY
      ↓
AuthManager.handle_callback()
      ├─ 验证state（10分钟有效期）
      ├─ 交换authorization code为access_token
      ├─ 获取用户信息
      ├─ 创建会话(SessionData)
      └─ 设置HttpOnly Cookie
      ↓
重定向到 /
```

### 会话管理

**会话存储**: 内存字典 `_sessions` + 线程锁

**会话数据结构**:
```python
class SessionData:
    access_token: str      # Gitea OAuth token
    refresh_token: Optional[str]
    scope: str
    expires_at: float      # Unix 时间戳
    user: {
        username: str
        full_name: str
        avatar_url: str
    }
```

**会话验证**:
- Cookie读取 session_id
- 从内存中查找 SessionData
- 检查过期时间
- 如果过期自动删除

### 双客户端模式

```
┌─ 用户已登录 (OAuth会话有效)
│  └─ 使用用户的 Gitea access_token 创建 GiteaClient
│     └─ 调用 GitAPI 受限于用户权限
│
└─ 用户未登录 (OAuth关闭或会话过期)
   └─ 使用全局 gitea_token (设置中的 GITEA_TOKEN)
      └─ 调用 GitAPI 受限于Bot权限
```

**代码示例**（来自 `app/api/routes.py`）:
```python
client = (
    context.auth_manager.build_user_client(session)
    if context.auth_manager.enabled
    else context.gitea_client
)
repos = await client.list_user_repos()  # 使用对应权限查询
```

---

## 4. 整体调用流程

### 启动流程

```
python -m app.main (或 uvicorn app.main:app)
      ↓
FastAPI 创建应用 (create_app)
      ↓
lifespan 上下文管理器启动
      ├─ 打印版本信息和配置
      ├─ 初始化 Database
      │  ├─ 创建异步引擎
      │  ├─ 创建会话工厂
      │  └─ 创建所有表
      ├─ 尝试 JSON→数据库 迁移
      └─ 更新 AppContext 的数据库引用
      ↓
应用运行
      ↓
按 Ctrl+C 或收到 SIGTERM
      ↓
lifespan 上下文管理器关闭
      ├─ 关闭数据库连接
      └─ 输出关闭日志
```

**关键文件**: `app/main.py`

### webhook处理流程

#### 自动触发（Pull Request 事件）

```
Gitea 发送 webhook (X-Gitea-Event: pull_request)
      ↓
POST /webhook (endpoint)
      ├─ 读取请求体
      ├─ 验证 HMAC 签名
      ├─ 解析 X-Review-Features / X-Review-Focus headers
      └─ 返回 202 Accepted（立即返回）
      ↓ (后台异步任务)
BackgroundTasks.add_task(process_webhook_async, payload, features, focus)
      ↓
WebhookHandler.process_webhook_async()
      ↓
WebhookHandler.handle_pull_request()
      ├─ 仅处理 action="opened" 或 "synchronized"
      └─ 调用 _perform_review()
      ↓
[见核心审查流程]
```

#### 手动触发（Issue Comment 事件）

```
Gitea 发送 webhook (X-Gitea-Event: issue_comment)
      ↓
POST /webhook (endpoint)
      ├─ 读取请求体
      ├─ 验证签名
      └─ 返回 202 Accepted
      ↓ (后台异步任务)
BackgroundTasks.add_task(process_comment_async, payload)
      ↓
WebhookHandler.process_comment_async()
      ↓
WebhookHandler.handle_issue_comment()
      ├─ 仅处理 action="created"
      ├─ 使用 CommandParser 解析评论命令 (/review --features ... --focus ...)
      ├─ 验证是否在 PR 中 (issue.pull_request 必须存在)
      ├─ 获取完整 PR 信息
      └─ 调用 _perform_review()
      ↓
[见核心审查流程]
```

#### 核心审查流程 (_perform_review)

```
_perform_review(owner, repo_name, pr_number, pr_data, features, focus_areas, trigger_type)

1. 创建数据库记录
   ├─ DBService.get_or_create_repository(owner, repo_name)
   └─ DBService.create_review_session(
        pr_number, trigger_type, enabled_features, focus_areas
      )
      → 返回 review_session_id

2. 发送初始状态（如果启用）
   ├─ features="comment" → 创建初始评论 "正在审查中..."
   ├─ features="status"  → 设置 commit 状态为 "pending"
   └─ 记录 Gitea API 调用数

3. 获取PR diff
   └─ GiteaClient.get_pull_request_diff(owner, repo_name, pr_number)
   → diff_content

4. 尝试克隆仓库
   ├─ RepoManager.clone_repository(clone_url, owner, repo_name, pr_number)
   ├─ 如果成功：分析模式 = "full"
   └─ 如果失败：分析模式 = "simple"（仅diff）

5. 分析 PR
   ├─ full 模式: ClaudeAnalyzer.analyze_pr(repo_path, diff, focus_areas)
   │            cwd=repo_path（提供完整代码库上下文）
   └─ simple 模式: ClaudeAnalyzer.analyze_pr_simple(diff, focus_areas)
                  仅分析diff内容
   → ClaudeReviewResult

6. 发布结果
   ├─ features="comment" → 更新评论为审查结果 (Markdown)
   ├─ features="review"  → 创建 PR review + inline comments
   ├─ features="status"  → 设置 commit 状态
   │                      (success/error 根据 severity 决定)
   └─ 记录 Gitea API 调用数

7. 数据库记录更新
   └─ DBService.update_review_session(
        review_session_id,
        analysis_mode="full"/"simple",
        diff_size_bytes=len(diff),
        overall_severity=result.severity,
        summary_markdown=result.summary,
        inline_comments_count=len(result.inline_comments),
        overall_success=True/False,
        completed=True
      )

8. 清理
   ├─ RepoManager.cleanup(repo_path)
   └─ 记录统计信息
```

### 服务组件架构

```
AppContext (容器)
│
├─ GiteaClient
│  └─ 所有 Gitea API 调用 (get_pull_request, create_comment, etc.)
│
├─ RepoManager
│  └─ 克隆仓库、清理临时文件
│
├─ ClaudeAnalyzer
│  └─ 调用 Claude CLI，分析 PR diff
│
├─ WebhookHandler
│  ├─ handle_pull_request() / handle_issue_comment()
│  └─ _perform_review() (核心逻辑)
│
├─ RepoRegistry
│  └─ 管理 webhook secrets (JSON文件或数据库)
│
├─ AuthManager
│  └─ OAuth 流程、会话管理
│
└─ Database
   ├─ 异步连接池
   └─ 会话上下文管理器
```

---

## 5. API 端点

### 公开端点（无认证）
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/version` | 版本信息 |
| `GET` | `/changelog` | 完整更新日志 |
| `POST` | `/webhook` | Gitea webhook 接收器 |

### 认证端点（可选OAuth）
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/config/public` | 前端配置 |
| `GET` | `/api/auth/status` | 当前用户状态 |
| `GET` | `/api/auth/login-url` | OAuth 授权链接 |
| `POST` | `/api/auth/logout` | 注销 |
| `GET` | `/api/auth/callback` | OAuth 回调 |
| `GET` | `/api/repos` | 当前用户可管理的仓库 |
| `GET` | `/api/repos/{owner}/{repo}/permissions` | 权限检查 |
| `POST` | `/api/repos/{owner}/{repo}/setup` | 配置 webhook |

### 数据查询端点
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/reviews` | 审查历史列表 |
| `GET` | `/api/reviews/{review_id}` | 审查详情 |
| `GET` | `/api/stats` | 使用量统计 |
| `GET` | `/api/configs` | 模型配置列表 |
| `POST` | `/api/configs` | 创建/更新模型配置 |
| `GET` | `/api/repositories` | 已配置仓库列表 |

---

## 6. 数据流示例

### 场景：用户手动触发审查

```
用户在 PR 评论中输入：
@pr-reviewer-bot /review --features comment,review --focus security

     ↓

Gitea webhook
POST /webhook
  X-Gitea-Event: issue_comment
  body: {
    action: "created",
    comment: { body: "@pr-reviewer-bot /review ..." },
    issue: { number: 42, pull_request: {...} },
    repository: { name: "myrepo", owner: {...} }
  }

     ↓

验证签名 (使用 repo_registry.get_secret(owner, repo))

     ↓

后台任务: process_comment_async(payload)
  → CommandParser.parse_comment("@pr-reviewer-bot /review ...")
  → ReviewCommand {
      command: "/review",
      features: ["comment", "review"],
      focus_areas: ["security"]
    }

     ↓

_perform_review(
  owner="user",
  repo_name="myrepo",
  pr_number=42,
  pr_data={...},
  features=["comment", "review"],
  focus_areas=["security"],
  trigger_type="manual"
)

     ↓

数据库: 创建 ReviewSession(
  repository_id=1,
  pr_number=42,
  trigger_type="manual",
  enabled_features='["comment","review"]',
  focus_areas='["security"]'
)

     ↓

GiteaClient.get_pull_request_diff() → diff_content

     ↓

ClaudeAnalyzer.analyze_pr(repo_path, diff, ["security"])
  → ClaudeReviewResult {
      severity: "high",
      summary: "...",
      inline_comments: [
        {
          path: "src/app.py",
          new_line: 15,
          severity: "high",
          comment: "SQL injection risk",
          suggestion: "Use parameterized queries"
        }
      ]
    }

     ↓

发布结果:
  1. 更新评论 (feature="comment")
  2. 创建 PR review + inline comments (feature="review")
  3. 不设置 status (feature 不包含 "status")

     ↓

数据库更新:
  ReviewSession.update(
    analysis_mode="full",
    overall_severity="high",
    summary_markdown="...",
    inline_comments_count=1,
    overall_success=True,
    completed=True
  )

  InlineComment.insert({
    review_session_id=1,
    file_path="src/app.py",
    new_line=15,
    severity="high",
    comment="SQL injection risk",
    suggestion="Use parameterized queries"
  })
```

---

## 7. 配置优先级

对于同一设置项的优先级（从高到低）：

```
1. 仓库级 ModelConfig (通过数据库)
   └─ 针对特定仓库的自定义配置

2. 全局 ModelConfig (通过数据库)
   └─ is_default=True 的全局配置

3. 环境变量 (.env 文件)
   └─ DEFAULT_REVIEW_FOCUS 等

4. 代码硬编码默认值
   └─ ["comment"] 功能
   └─ ["quality", "security", "performance", "logic"] 审查重点
```

---

## 附录：版本演进对比

### v1.0.0 ~ v1.3.x（旧架构）

```
.env 文件 → Settings → 各服务直接使用
```

- 配置全部存储在 `.env`
- 无持久化存储
- 无用户系统

### v1.4.0+（新架构）

```
.env 文件（基础配置）
     ↓
Settings (Pydantic)
     ↓
Database (SQLAlchemy async)
     ├── Repository（仓库配置）
     ├── ModelConfig（AI模型配置）
     ├── ReviewSession（审查会话记录）
     ├── InlineComment（行级评论）
     └── UsageStat（使用统计）
```

| 项目 | 旧 (.env) | 新 (数据库) |
|------|----------|------------|
| Gitea连接 | `GITEA_URL`, `GITEA_TOKEN` | 仍在 .env |
| Claude配置 | `CLAUDE_CODE_PATH` | 仍在 .env |
| 仓库配置 | 无 | `Repository` 表 |
| AI模型配置 | 无 | `ModelConfig` 表 |
| 审查历史 | 无 | `ReviewSession` + `InlineComment` |
| 使用统计 | 无 | `UsageStat` 表 |
| 用户认证 | 无 | OAuth + 会话管理 |

---

## 关键文件索引

| 文件路径 | 职责 |
|---------|------|
| `app/main.py` | 应用入口、生命周期管理 |
| `app/core/config.py` | 配置加载（Pydantic Settings） |
| `app/core/database.py` | 数据库初始化、会话管理 |
| `app/models/` | ORM 模型定义 |
| `app/services/db_service.py` | 数据库操作封装 |
| `app/services/webhook_handler.py` | Webhook处理、核心审查逻辑 |
| `app/services/gitea_client.py` | Gitea API 客户端 |
| `app/services/claude_analyzer.py` | Claude CLI 调用 |
| `app/services/auth_manager.py` | OAuth 认证管理 |
| `app/api/routes.py` | API 路由定义 |

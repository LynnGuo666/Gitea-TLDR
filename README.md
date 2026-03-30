# LCPU AI Reviewer

基于多引擎（Claude Code / Codex CLI）的 Gitea Pull Request 自动审查工具。当用户提交 PR 后，该工具会自动接收 webhook 通知，使用 AI 模型分析代码变更，并将审查结果反馈到 Gitea。

**当前版本**: v1.21.6 | **发布日期**: 2026-03-20

## 功能特性

- **自动化审查**: 接收 Gitea webhook，PR 创建/更新时自动触发审查
- **手动触发**: 通过评论 `/review` 命令（可配合 `@bot` 提及）手动触发审查
- **多审查引擎**: 支持 Claude Code 和 Codex CLI，可按仓库灵活配置
- **完整上下文分析**: 克隆完整代码库，为 AI 提供充分的项目上下文
- **灵活反馈机制**: 通过 HTTP 标头或命令参数控制审查功能
  - PR 评论（Comment）
  - PR 审查（Review）
  - 提交状态（Status）
- **多维度审查**:
  - 代码质量和最佳实践
  - 安全漏洞检测
  - 性能问题分析
  - 逻辑错误和 bug 发现
- **异步处理**: 立即返回 202 响应，后台处理审查任务，避免 webhook 超时
- **OAuth 用户登录**: 前端用户可使用自己的 Gitea 账号登录
- **管理后台**: Dashboard、用户管理、仓库管理、配置管理、Webhook 日志

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy/Alembic + PyNaCl 加密 |
| 前端 | Next.js (Pages Router) + HeroUI + Tailwind CSS |
| 数据库 | SQLite（默认）+ 异步引擎 aiosqlite |
| 审查引擎 | Claude Code CLI / Codex CLI |
| 部署 | Docker + Docker Compose |

## 项目结构

```
gitea-tldr/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── core/
│   │   ├── config.py          # 配置管理（环境变量）
│   │   ├── context.py         # 应用上下文
│   │   ├── database.py        # 异步数据库连接
│   │   ├── encryption.py       # PyNaCl 敏感数据加密
│   │   ├── version.py         # 版本信息
│   │   ├── admin_auth.py      # 管理员权限校验
│   │   └── admin_settings.py  # 管理员设置
│   ├── api/
│   │   ├── routes.py          # 主 API 路由
│   │   └── admin_routes.py    # 管理后台 API
│   ├── models/                # SQLAlchemy ORM 模型
│   │   ├── user.py            # 用户
│   │   ├── user_session.py    # 会话（加密存储 access_token）
│   │   ├── repository.py       # 仓库（加密存储 webhook_secret）
│   │   ├── model_config.py    # AI 模型配置（加密存储 api_key）
│   │   ├── api_key.py         # API Key 池（加密存储 provider_auth_token）
│   │   ├── review_session.py  # 审查会话
│   │   ├── inline_comment.py  # 行级评论
│   │   ├── usage_stat.py      # 用量统计
│   │   └── webhook_log.py     # Webhook 日志
│   └── services/
│       ├── auth_manager.py    # OAuth 认证管理
│       ├── db_service.py      # 数据库操作服务
│       ├── gitea_client.py     # Gitea API 客户端
│       ├── webhook_handler.py  # Webhook 处理器
│       ├── review_engine.py   # 审查引擎调度
│       ├── repo_manager.py    # 代码库克隆管理
│       ├── admin_service.py   # 管理后台服务
│       └── providers/         # 审查引擎实现
│           ├── base.py         # Provider 抽象基类
│           ├── claude_code.py  # Claude Code 实现
│           ├── codex_cli.py    # Codex CLI 实现
│           └── registry.py    # Provider 注册表
├── frontend/
│   ├── pages/                 # Next.js Pages Router
│   │   ├── index.tsx         # 首页/仪表盘
│   │   ├── reviews.tsx        # 审查历史
│   │   ├── settings.tsx       # 个人设置
│   │   ├── preferences.tsx    # 用户中心
│   │   ├── usage.tsx          # 用量统计
│   │   ├── repo/[owner]/[repo].tsx  # 仓库详情
│   │   └── admin/             # 管理后台页面
│   ├── components/            # React 组件
│   └── lib/version.ts         # 前端版本信息
├── alembic/versions/         # 数据库迁移脚本
├── tests/                    # 测试套件
├── requirements.txt          # Python 依赖
├── package.json              # 前端依赖
├── docker-compose.yml        # Docker Compose 配置
├── Dockerfile                # 镜像构建
└── README.md
```

## 安装部署

### 1. 环境要求

- Python 3.11+
- Node.js 20+（前端构建）
- Git
- Claude Code CLI 或 Codex CLI（至少安装一个）

### 2. 安装依赖

```bash
# 克隆仓库
git clone <repository-url>
cd gitea-tldr

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..
```

### 3. 配置环境变量

创建 `.env` 文件：

```env
# ============ 必需配置 ============

# Gitea 服务器地址
GITEA_URL=https://gitea.example.com

# Gitea 访问令牌（Bot 用户或 Personal Access Token）
GITEA_TOKEN=your_gitea_access_token_here

# ============ 可选配置 ============

# Webhook 签名密钥（用于验证 webhook 请求来源）
WEBHOOK_SECRET=your_webhook_secret_here

# Claude Code CLI 路径（默认: claude）
CLAUDE_CODE_PATH=claude

# 是否启用 Claude usage 捕获代理（默认: true，需旁路排障时可设为 false）
CLAUDE_USAGE_PROXY_ENABLED=true

# 是否输出 Claude usage 代理诊断日志（默认: false）
CLAUDE_USAGE_PROXY_DEBUG=false

# Codex CLI 路径（默认: codex）
CODEX_CLI_PATH=codex

# 默认审查引擎（claude_code | codex_cli）
DEFAULT_PROVIDER=claude_code

# 工作目录（默认: ./review-workspace）
WORK_DIR=./review-workspace

# 数据库连接 URL（默认: sqlite+aiosqlite:///work_dir/gitea_pr_reviewer.db）
# DATABASE_URL=sqlite+aiosqlite:///path/to/database.db

# ============ 服务器配置 ============

HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
DEBUG=false

# ============ OAuth 配置（可选） ============
# 用于前端用户使用自己的 Gitea 账号登录

OAUTH_CLIENT_ID=your_oauth_client_id
OAUTH_CLIENT_SECRET=your_oauth_client_secret
OAUTH_REDIRECT_URL=http://localhost:8000/api/auth/callback
# OAuth 申请的 scope 列表
OAUTH_SCOPES=read:user,read:repository
SESSION_COOKIE_NAME=gitea_session
SESSION_COOKIE_SECURE=false

# ============ 管理后台配置 ============

# 是否启用管理后台（默认: true）
ADMIN_ENABLED=true
# 初始管理员用户名（首次启动时自动创建）
INITIAL_ADMIN_USERNAME=admin

# ============ 审查配置 ============

# Bot 用户名（用于识别 @提及，触发手动审查）
BOT_USERNAME=pr-reviewer-bot

# 默认审查重点（逗号分隔）
DEFAULT_REVIEW_FOCUS=quality,security,performance,logic

# 自动请求审查者（创建 review 后自动将 bot 添加为审查者）
AUTO_REQUEST_REVIEWER=true

# Webhook 日志保留天数
WEBHOOK_LOG_RETENTION_DAYS=30
WEBHOOK_LOG_RETENTION_DAYS_FAILED=90
```

### 4. 数据库初始化

应用启动时自动运行 Alembic 迁移，无需手动执行。

```bash
# 查看当前数据库版本
alembic current

# 升级到最新版本
alembic upgrade head

# 查看迁移历史
alembic history --verbose

# 创建新的迁移（开发使用）
alembic revision --autogenerate -m "描述变更内容"
```

### 5. 启动服务

```bash
# 开发模式
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. 构建前端 UI

```bash
cd frontend
npm install
npm run build   # 生成 out/ 目录
```

服务启动后，访问 `http://localhost:8000/ui` 即可使用前端控制台。

### 7. 配置 Gitea Webhook

在 Gitea 仓库设置中添加 Webhook：

1. 进入仓库 → 设置 → Webhooks → 添加 Webhook → 选择 "Gitea"
2. 配置参数：
   - **目标 URL**: `http://your-server:8000/webhook`
   - **HTTP 方法**: POST
   - **内容类型**: application/json
   - **密钥**: 与 `.env` 中的 `WEBHOOK_SECRET` 一致
   - **触发事件**:
     - ✅ Pull Request（自动触发）
     - ✅ Issue Comment（手动触发 `/review`）
   - **自定义标头**（可选）:
     - `X-Review-Features: comment,review,status`
     - `X-Review-Focus: quality,security,performance,logic`

## 使用说明

### 自动触发（Webhook）

PR 被创建或更新时，工具自动触发审查。

### 手动触发（评论命令）

在 PR 评论中使用：

```
/review
```

或配合 `@bot` 提及：

```
@pr-reviewer-bot /review
```

指定审查功能：

```
@pr-reviewer-bot /review --features comment,status
```

指定审查重点：

```
@pr-reviewer-bot /review --focus security,performance
```

### Webhook 标头配置

| 标头 | 说明 | 可选值 |
|------|------|--------|
| `X-Review-Features` | 启用的审查功能 | `comment`, `review`, `status`（逗号分隔） |
| `X-Review-Focus` | 审查重点 | `quality`, `security`, `performance`, `logic`（逗号分隔） |

### OAuth 登录

若希望前端用户使用自己的 Gitea 账号操作：

1. 在 Gitea `Settings → Applications → Manage OAuth2 Applications` 创建应用
2. 设置 Redirect URL 为 `http(s)://your-server/api/auth/callback`
3. 将 Client ID / Secret 写入 `.env` 的 `OAUTH_*` 配置
4. 重启服务后，侧边栏出现 "连接 Gitea" 按钮

## API 端点

### 认证相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/status` | 获取当前登录状态 |
| GET | `/api/auth/admin-status` | 获取管理员状态 |
| GET | `/api/auth/login-url` | 获取 OAuth 授权 URL |
| POST | `/api/auth/logout` | 注销会话 |
| GET | `/api/auth/callback` | OAuth 回调 |

### 仓库相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/repos` | 列出用户可访问的仓库 |
| GET | `/api/repos/{owner}/{repo}/permissions` | 检查仓库权限 |
| POST | `/api/repos/{owner}/{repo}/setup` | 配置仓库（创建 Webhook） |
| GET | `/api/repos/{owner}/{repo}/webhook-status` | 查询 Webhook 状态 |
| DELETE | `/api/repos/{owner}/{repo}/webhook` | 删除 Webhook |
| POST | `/api/repos/{owner}/{repo}/validate-admin` | 校验仓库管理权限 |
| GET | `/api/repos/{owner}/{repo}/pulls` | 获取 PR 列表 |
| GET | `/api/repos/{owner}/{repo}/provider-config` | 获取 AI 配置 |
| PUT | `/api/repos/{owner}/{repo}/provider-config` | 更新 AI 配置 |
| GET | `/api/repos/{owner}/{repo}/review-settings` | 获取审查设置 |
| PUT | `/api/repos/{owner}/{repo}/review-settings` | 更新审查设置 |
| GET | `/api/repos/{owner}/{repo}/webhook-secret` | 获取 Webhook 密钥 |
| POST | `/api/repos/{owner}/{repo}/webhook-secret/regenerate` | 重新生成 Webhook 密钥 |

### 审查相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/reviews` | 列出所有审查会话（管理员） |
| GET | `/api/reviews/{review_id}` | 获取审查详情（管理员） |
| GET | `/api/my/reviews` | 获取当前用户的审查会话 |
| GET | `/api/my/reviews/{review_id}` | 获取当前用户的指定审查详情 |

### 配置相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/public` | 获取公开配置 |
| GET | `/api/providers` | 获取可用的审查引擎列表 |
| GET | `/api/config/provider-global` | 获取全局 AI 配置（管理员） |
| PUT | `/api/config/provider-global` | 更新全局 AI 配置（管理员） |
| GET | `/api/configs` | 列出所有配置（管理员） |
| POST | `/api/configs` | 创建配置（管理员） |

### 统计相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 获取用量统计（需登录） |

### 系统相关

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/health` | 健康检查 |
| GET | `/version` | 版本信息 |
| GET | `/changelog` | 完整更新日志 |

### Webhook

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/webhook` | 接收 Gitea Webhook |

## Docker 部署

### 使用 Docker Compose（推荐）

```bash
# 创建并配置 .env 文件
cp .env.example .env
# 编辑 .env 填写配置

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

### 使用 Docker 命令

```bash
# 构建镜像
docker build -t gitea-tldr .

# 运行容器
docker run -d \
  --name gitea-tldr \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/tmp/gitea-tldr \
  gitea-tldr
```

### 拉取预构建镜像

```bash
# 从 GitHub Container Registry 拉取
docker pull ghcr.io/lynnguo666/gitea-tldr:main

# 运行
docker run -d \
  --name gitea-tldr \
  -p 8000:8000 \
  --env-file .env \
  ghcr.io/lynnguo666/gitea-tldr:main
```

## 安全特性

- **敏感数据加密**: `access_token`、`refresh_token`、`api_key`、`webhook_secret` 等字段使用 PyNaCl（X25519 + XSalsa20-Poly1305）加密存储，密钥位于 `work_dir/encryption.key`，文件权限 `0600`
- **API 响应脱敏**: 敏感配置字段在 API 响应中返回脱敏掩码
- **Webhook 签名验证**: 支持 HMAC-SHA256 签名校验
- **权限控制**: 管理接口强校验管理员身份，仓库配置接口校验仓库/组织权限
- **Fail-Closed**: 鉴权失败默认拒绝访问，不泄露信息
- **审计日志**: Webhook 请求完整记录（状态、耗时、payload 摘要）
- **会话管理**: 支持会话持久化到数据库，重启后可恢复

## 开发

### 运行测试

```bash
# 安装测试依赖（如 pytest-asyncio）
pip install pytest pytest-asyncio

# 运行所有测试
pytest tests/ -v

# 运行加密测试
pytest tests/test_encryption.py -v
```

### 代码检查

```bash
# Python 类型检查
python -m mypy app

# 前端 TypeScript 检查
cd frontend && npm run lint && npx tsc --noEmit
```

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| Webhook 未触发 | 检查 Gitea Webhook 配置、服务器端口可达性、WEBHOOK_SECRET 一致性 |
| 仓库克隆失败 | 确认 GITEA_TOKEN 权限充足、网络连接正常、工作目录磁盘空间充足 |
| Claude/Codex 调用失败 | 确认 CLI 已安装（`claude --version` 或 `codex --version`）、路径配置正确 |
| OAuth 登录失败 | 检查 OAUTH_CLIENT_ID/SECRET/REDIRECT_URL 配置是否正确 |
| 数据库迁移失败 | 查看 alembic 日志，确保数据库文件目录有写入权限 |

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。

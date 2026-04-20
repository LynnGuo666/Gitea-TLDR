# LCPU AI Reviewer

基于多引擎（Forge / Claude Code / Codex CLI）的 Gitea Pull Request 自动审查 & Issue 分析工具。

**当前版本**: v1.27.0 | **发布日期**: 2026-04-20

## 功能特性

- **PR 自动审查**: 接收 Gitea webhook，PR 创建/更新时自动触发
- **Issue 智能分析**: 对 Issue 进行 AI 分析，自动归类、提供解决方案、支持 `/issue --focus bug,duplicate,design` 参数
- **手动触发**: PR 评论中使用 `/review` 命令触发审查，Issue 评论中使用 `/issue` 触发分析
- **多审查引擎**: 支持 Forge、Claude Code、Codex CLI，可按仓库灵活配置；Issue 分析目前仅 Forge 引擎支持
- **完整上下文**: 克隆完整代码库，为 AI 提供充分的项目上下文
- **多维度审查**: 代码质量、安全漏洞、性能问题、逻辑错误
- **灵活输出**: PR 评论、PR 审查、提交状态（可通过标头或命令参数控制）
- **管理后台**: Dashboard、用户管理、仓库管理、配置管理、Webhook 日志
- **OAuth 登录**: 支持使用 Gitea 账号登录前端

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy/Alembic + PyNaCl 加密 |
| 前端 | Next.js (Pages Router) + HeroUI + Tailwind CSS |
| 数据库 | SQLite（默认）+ aiosqlite 异步引擎 |
| 审查引擎 | Forge（内置）/ Claude Code CLI / Codex CLI |
| 部署 | Docker + Docker Compose |

## 安装部署

### 环境要求

- Python 3.11+、Node.js 20+、Git
- Forge 无需额外安装；如需 Claude Code / Codex CLI 请自行安装

### 快速开始

```bash
git clone <repository-url> && cd gitea-tldr

# 安装依赖
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# 配置
cp .env.example .env   # 编辑 .env 填写必要配置

# 启动（数据库迁移自动执行）
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

前端控制台地址：`http://localhost:8000/ui`

### 关键环境变量

```env
# 必需
GITEA_URL=https://gitea.example.com
GITEA_TOKEN=your_gitea_access_token_here

# 可选
WEBHOOK_SECRET=your_webhook_secret_here
DEFAULT_PROVIDER=forge          # forge | claude_code | codex_cli
BOT_USERNAME=pr-reviewer-bot
WORK_DIR=./review-workspace

# OAuth（前端登录）
OAUTH_CLIENT_ID=...
OAUTH_CLIENT_SECRET=...
OAUTH_REDIRECT_URL=http://localhost:8000/api/auth/callback

# 管理后台
ADMIN_ENABLED=true
INITIAL_ADMIN_USERNAME=admin
```

完整配置项见 `.env.example`。

### 配置 Gitea Webhook

仓库 → 设置 → Webhooks → 添加 Webhook（Gitea 类型）：

- **目标 URL**: `http://your-server:8000/webhook`
- **内容类型**: `application/json`
- **密钥**: 与 `WEBHOOK_SECRET` 一致
- **触发事件**: Pull Request + Issue Comment

可选标头：
```
X-Review-Features: comment,review,status
X-Review-Focus: quality,security,performance,logic
```

## 使用说明

### 手动触发审查

在 PR 评论中：

```
/review
@pr-reviewer-bot /review --features comment,status --focus security,performance
```

### Docker 部署

```bash
# Docker Compose（推荐）
cp .env.example .env
docker compose up -d

# 或拉取预构建镜像
docker pull ghcr.io/lynnguo666/gitea-tldr:main
docker run -d --name gitea-tldr -p 8000:8000 --env-file .env \
  -v $(pwd)/data:/tmp/gitea-tldr ghcr.io/lynnguo666/gitea-tldr:main
```

## 安全特性

- **敏感数据加密**: access_token、api_key、webhook_secret 等使用 PyNaCl（X25519 + XSalsa20-Poly1305）加密存储
- **Webhook 签名验证**: HMAC-SHA256 校验
- **权限控制**: 管理接口强校验身份，Fail-Closed 原则
- **API 响应脱敏**: 敏感字段返回掩码

## 开发

```bash
# 测试
pytest tests/ -v

# 代码检查
ruff check app && mypy app
cd frontend && npm run lint && npx tsc --noEmit
```

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| Webhook 未触发 | 检查 Gitea Webhook 配置、端口可达性、WEBHOOK_SECRET 一致性 |
| 仓库克隆失败 | 确认 GITEA_TOKEN 权限充足、磁盘空间足够 |
| 审查引擎调用失败 | 确认 CLI 已安装（`claude --version`/`codex --version`），路径配置正确 |
| OAuth 登录失败 | 检查 OAUTH_CLIENT_ID/SECRET/REDIRECT_URL 配置 |
| 数据库迁移失败 | 确保数据库目录有写入权限，查看 alembic 日志 |

## 许可证

MIT License — 如有问题请提交 Issue。

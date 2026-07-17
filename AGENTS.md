# 项目知识库

**生成时间:** 2026-07-17 CST
**提交:** `c7e219c`
**分支:** `main`

## 概览
- 技术栈：FastAPI + SQLAlchemy/Alembic 后端，Next.js pages-router 前端（静态导出），Docker 部署。
- 核心领域：Gitea PR 审查编排（默认 Forge 引擎；`claude_code`、`codex_cli` 为 legacy extras，需 `ENABLE_LEGACY_PROVIDERS=true` 启用）+ 管理后台/用量面板。

## 目录结构
```text
.
├── app/                 # 后端（api/core/services/models/review/gitea）
├── frontend/            # Next.js UI（pages/components/lib）
├── alembic/             # 数据库迁移
├── scripts/             # 运维脚本
├── agents/plan/         # 架构约束文档
├── docker/              # Docker 构建与编排
├── Clawd-Code/          # 内嵌实验项目（独立 git 仓库）
├── .sisyphus/plans/     # 设计文档
└── AGENTS.md            # 根约定 + 层级索引
```

## 层级索引
- `app/AGENTS.md` — 后端分层规则、API/service/model 边界。
- `app/review/AGENTS.md` — 审查编排核心（webhook 处理、Issue 分析、引擎调度）。
- `app/review/providers/AGENTS.md` — 审查引擎契约与安全约束。
- `app/gitea/AGENTS.md` — Gitea 客户端集成（认证、API 调用、仓库管理）。
- `frontend/AGENTS.md` — UI 分层、路由约定、共享 lib/component 规则。
- `frontend/pages/AGENTS.md` — 页面级模式（认证、加载/错误/空状态、动态路由）。

## 代码定位
| 任务 | 位置 | 说明 |
|------|------|------|
| 应用启动 | `app/main.py` | 上下文创建、中间件、静态文件挂载 |
| API 路由（全部） | `app/api/routes.py` | 单一文件包含所有路由（含 admin） |
| 数据库模型 | `app/models/` | ORM 实体与关系 |
| 业务编排 | `app/services/` | webhook、gitea、db、auth、admin |
| 审查引擎 | `app/review/providers/` | Forge 默认；CLI 实现位于 `extras/`，按需启用 |
| 审查编排 | `app/review/` | webhook_handler、issue_service、review_engine |
| Gitea 客户端 | `app/gitea/` | API 封装、认证、仓库注册 |
| 前端外壳 | `frontend/pages/_app.tsx`、`frontend/components/Layout.tsx` | providers、auth 刷新、导航 |
| 页面路由 | `frontend/pages/` | pages-router，含动态路由 |

## 全局规则
- Codex/OpenCode 操作前必须阅读 `agents/plan/` 下所有文件；更新后需重新阅读。
- 若指南与代码行为冲突，遵循指南，并在 PR 中记录差异。
- 版本同步必须跨以下三个文件：
  - `app/core/version.py`
  - `frontend/package.json`
  - `frontend/lib/version.ts`

## 项目特定约定
- 后端配置：在 `app/core/config.py` 中定义新环境变量字段，然后同步到 `.env.example` 和 README/文档。
- 前端 API 调用必须通过后端端点；禁止前端直接调用 Gitea/Claude。
- 页面标题语义严格：
  - 主页面标题使用 `frontend/components/PageHeader.tsx`（`h1`）
  - 章节标题使用 `frontend/components/SectionHeader.tsx`（`h2`）
- 管理后台入口可见性基于角色；使用 auth/admin 状态端点，而非客户端猜测。
- admin 路由未拆分独立文件，与主路由同处于 `app/api/routes.py`。

## 反模式（本条禁止）
- 不得在日志、URL、提交历史中泄露 token/密钥。
- `WEBHOOK_SECRET` 已配置时不得跳过 webhook 签名验证。
- Python 中不得使用 `from x import *`。
- 前端不得使用 `any`；使用显式类型 / `unknown` + 类型收窄。
- 不得编辑生成产物/供应商文件：
  - `.git/`、`.venv/`、`frontend/node_modules/`、`frontend/.next/`、`frontend/out/`、缓存文件。

## 构建与验证
```bash
# 后端（使用 uv 管理依赖）
uv run uvicorn app.main:app --reload
uv run ruff check app && uv run mypy app && uv run pytest

# 前端
cd frontend && npm run lint && npx tsc --noEmit && npm run build

# Docker 端到端
docker compose -f docker/docker-compose.yml up --build
```

### pre-commit（可选但推荐）
```bash
# 安装 git hook（首次）
pre-commit install
# 全量跑一遍
pre-commit run --all-files
```
钩子集：ruff check + format、`requirements-txt-fixer`、`check-merge-conflict`、
`detect-private-key`、`gitleaks`。CI 的 quality workflow 跑等价的后端 ruff/mypy/pytest
+ 前端 lint/tsc/build，pre-commit 是本地提交前的快速反馈层。

## 发布清单
- 更新 `CHANGELOG.md`（用户可见的变更）。
- 同步三个版本文件（后端 + 前端 + 前端 lib）。
- 版本变更后重新构建前端静态输出（`cd frontend && npm run build`）。

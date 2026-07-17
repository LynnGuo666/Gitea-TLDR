# 贡献指南

感谢参与 Gitea TLDR！本文档说明开发环境、提交规范、版本同步与 PR 流程。

## 开发环境

### 前置依赖

- Python 3.11+
- Node.js 20+
- Git
- [uv](https://docs.astral.sh/uv/)（Python 依赖与虚拟环境管理）

### 初始化

```bash
# 安装 Python 依赖（uv 会按 uv.lock 锁定版本，自动管理 Python 3.11）
uv sync --extra dev

# 安装前端依赖并构建静态产物
cd frontend && npm ci && npm run build && cd ..
```

配置文件：`cp .env.example .env`，按需填写。

## 开发验证

每次提交前请确保以下命令全部通过（CI 的 quality workflow 会跑同样的检查）：

```bash
# 后端：lint + 类型检查 + 测试
uv run ruff check app
uv run mypy app
uv run pytest -m "not live"

# 前端：lint + 类型检查 + 构建
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

`-m "not live"` 跳过需要真实 OAuth 交互的 live 测试；如需运行：

```bash
uv run pytest -m live -s
```

## 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)，例如：

```
feat(review): 新增 Forge 提示词自我验证步骤
fix(webhook): 修复 bot 自触发过滤遗漏
refactor(db): DBService 拆分三个 Repository
docs: 更新 README 到 2.4.0
chore: bump 2.5.0
```

- 提交信息用中文或英文均可，但请清晰描述「做了什么」与「为什么」。
- **禁止携带 `Co-Authored-By` 行**（包括默认的 Claude 署名）。
- 一个提交聚焦一件事，便于 review 与回滚。

## 版本同步

版本号必须跨以下三个文件同步（详见 `AGENTS.md`「版本同步必须跨以下三个文件」）：

- `app/core/version.py`（`__version__` + `VERSION_HISTORY`）
- `frontend/package.json`（`version` 字段）
- `frontend/lib/version.ts`

同时在 `CHANGELOG.md` 顶部添加新版本条目。版本变更后必须重新构建前端静态输出：

```bash
cd frontend && npm run build
```

## 测试

- 单元测试位于 `tests/`，使用 pytest。
- `tests/conftest.py` 提供 in-memory sqlite fixture 与 fake clients，新测试优先复用现有 fixture。
- 标记 `live` 的测试需要真实外部交互，CI 默认跳过。

## PR 流程

1. 从 `main` 拉取分支，命名建议 `feat/xxx`、`fix/xxx`、`refactor/xxx`。
2. 确保本地验证全绿（见「开发验证」）。
3. PR 标题遵循 Conventional Commits。
4. PR 描述说明：解决了什么问题、如何解决、如何验证。
5. CI 的 `quality` workflow 必须通过（ruff/mypy/pytest + 前端 lint/tsc/build）。
6. 若改动与 `AGENTS.md` 约定有差异，请在 PR 描述中说明。

## AGENTS.md 体系

本项目遵循 `AGENTS.md` 分层约定体系（根 `AGENTS.md` + 各子目录 `app/AGENTS.md`、`app/review/AGENTS.md`、`frontend/AGENTS.md` 等）。修改代码前请先阅读对应层级的 `AGENTS.md`，遵循其中的分层规则与反模式约束。

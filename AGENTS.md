# AGENTS 指南

> 本文面向所有在仓库中执行任务的智能体。若指南与代码冲突，请先遵循指南并在 PR 中说明差异。

## 1. 仓库结构与职责
- `app/`：FastAPI 后端。`api/` 暴露 HTTP 路由，`services/` 聚合 Gitea/Claude/Webhook 等业务逻辑，`core/` 存放配置和版本信息，`models/` 管理 ORM/Pydantic。
- `frontend/`：Next.js 13 仪表盘，`npm run build` 后产出静态目录 `frontend/out`。根服务若检测到该目录会自动挂载静态页面。
- 根目录含 `.env.example`、`requirements.txt`、`Dockerfile`、`docker-compose.yml`、`build.sh` 等部署资产；若新增脚本请更新 `build.sh`。
- 版本文件：`app/core/version.py`、`frontend/package.json`、`frontend/lib/version.ts` 必须同步版本号和发布日期，否则左侧侧边栏会提示版本不一致。

## 2. 环境准备
- Python 3.11+：`python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`。
- Node 18 LTS：`cd frontend && npm install`。
- Docker：`docker compose up --build` 在本地验证 API、worker、前端整体流程；若脚本有改动须在 `build.sh` 记录。
- 新环境变量流程：在 `app/core/config.py` 定义 → `.env.example` 填默认/说明 → README 与本文说明用途。

## 3. 构建、运行、测试命令
1. **后端运行**
   - 热重载：`uvicorn app.main:app --reload`
   - 快速检查：`python app/main.py`（输出版本和 DEBUG 状态）
2. **后端测试**
   - 全量：`pytest`
   - 单文件：`pytest tests/test_webhook.py`
   - 单用例：`pytest tests/test_webhook.py -k test_signature_validation`
   - 带日志：`pytest -vv --log-cli-level=INFO`
3. **后端静态检查**
   - Lint：`ruff check app tests`
   - 类型：`mypy app`
   - 格式：`ruff format app tests` 或 `black app tests`
4. **前端命令**
   - 开发：`cd frontend && npm run dev`
   - 构建：`cd frontend && npm run build`（内部等价 `next build && next export && node create-repo-fallback.js`）
   - Lint：`cd frontend && npm run lint`
   - TypeScript：`cd frontend && npx tsc --noEmit`
5. **端到端验证**
   - Docker：`docker compose up --build --attach app`
   - 静态产物：`npx serve frontend/out`

## 4. Git 流程与版本策略
- 分支命名以语义加类型：`feature/<topic>`、`fix/<issue>`、`docs/<topic>`。
- Commit 使用 `feat:/fix:/chore:/refactor:/docs:` 等语义化前缀，并提及影响模块，例如 `feat: webhook handler retries`。
- PR 模板：问题背景 → 解决方案 → 测试命令及结果 → 配置/迁移说明 → 版本同步情况。
- 发布涉及用户体验的改动时，务必更新 `CHANGELOG.md`、三处版本文件与 README，对应 section 中写明变化。

## 5. Python 代码规范
1. **导入顺序**：标准库 → 第三方 → 项目内模块；每组之间空行，禁止 `from x import *`。
2. **类型标注**：所有函数/方法都需 type hints；异步函数返回值要精确，避免 `Any`；若确实不确定可用 `typing.Any` 并说明原因。
3. **日志**：模块顶部 `logger = logging.getLogger(__name__)`；敏感内容必须被 `if settings.debug:` 守卫；异常用 `logger.exception` 或 `logger.error(..., exc_info=True)`。
4. **错误处理**：FastAPI 路由抛 `HTTPException`；调用外部 API 时捕获 `httpx.HTTPError`，必要时写入 Webhook 日志与 `DBService`。
5. **配置读写**：新增配置项写入 `app/core/config.py` 且命名全大写；业务代码统一从 `settings.<FIELD>` 获取。
6. **数据库**：统一使用 AsyncSession，时间字段采用 `datetime.utcnow()`；写操作结束记得 `await session.commit()`；批量操作封装在 `AdminService` 或 `DBService`。
7. **结构与命名**：
   - 复杂逻辑拆分到 `app/services/xxx_service.py`
   - 事件处理函数命名为 `handle_<event>`，异步函数以 `async def` 开头
   - 常量全大写，枚举优先使用 `Enum`
8. **Docstring**：公共 API/服务函数使用 Google 风格或 PEP257，说明参数、返回值、抛出的异常。

## 6. 前端代码规范（Next.js + TypeScript）
1. 文件命名：组件使用 `PascalCase.tsx`；共享逻辑放 `frontend/lib/`；自定义 Hooks 可放 `frontend/hooks/`。
2. Props/State 必须显式声明类型；严禁 `any`，必要时使用 `unknown` 并在运行时缩小类型。
3. UI 状态：需要覆蓋 `loading`、`error`、`empty` 三种情形，尤其在用量图表与 Webhook 列表。
4. 样式：沿用 CSS Modules 与 Tailwind Merge；不要修改全局主题色，保持当前浅色体系。
5. 数据获取：只能调用后端 API；禁止直接访问 Gitea/Claude；新增 API 需先在后端实现。
6. Lint/格式：`npm run lint` 与 `tsc --noEmit` 必须通过；若使用 Prettier，请遵循仓库默认配置（printWidth 100）。
7. 版本信息：前端自动读取版本文件；修改版本后务必重新 `npm run build`。

## 7. 测试策略
- Webhook/Claude 测试：`pytest` 搭配 `httpx_mock` 构造 Gitea/Anthropic 响应；如需模拟 Claude CLI，构造 stdout/stderr。
- DB 层：使用 SQLite 内存库或 pytest fixture，测试后清理。
- 前端暂未配置自动化测试；如要添加 Jest/Playwright，请在 README 与本文说明命令。
- 手动验证：针对关键流程（`POST /webhook`、Admin 面板、Usage 统计）需记录操作步骤，方便回溯。
- 日志断言：在测试中验证签名校验、usage 记录等关键日志，确保可观测性。

## 8. 安全与配置提示
- 禁止在日志、URL、git 历史中泄露 token。`repo_manager.py` 已对 clone URL 进行掩码，新增代码需复用该逻辑。
- Webhook 验签：若配置了 `settings.webhook_secret`，缺失 `X-Gitea-Signature` 时立即 401；新增逻辑不得绕过此流程。
- OAuth session 当前存于内存，若实现 Redis/数据库持久化，要考虑多实例一致性并更新文档。
- Claude Proxy（规划中）：未来 Claude CLI 会将 base URL 指向本服务代理，代理层必须无损转发 HTTP 头和主体，同时记录 usage。
- 生产部署前设置 `DEBUG=false`，并确保 `.env` 中无默认弱密码。

## 9. 运维与 CI/CD
- `build.sh` 需完整描述构建顺序（安装依赖→运行测试→前端打包→镜像构建）；新增步骤务必注释。
- Docker 镜像：后端基于 `python:3.11-slim`，前端静态输出复制到 `/app/frontend/out`；不要在镜像里保留 `.venv` 或开发依赖。
- `docker-compose.yml` 当前包含 API、worker、frontend；若新增缓存/队列等服务，需同步更新 README 与端口说明。
- CI：`.github/workflows/docker-build.yml` 目前只构建镜像；如添加 lint/test 步骤，请确保本地命令一致并在本文记录。

## 10. 故障排查速查表
1. Webhook 返回 401：使用同一 payload 重新计算 HMAC-SHA256，确认 `X-Gitea-Signature` 与 `settings.webhook_secret` 对应。
2. Claude 请求失败：检查 `ANTHROPIC_API_KEY` 与 base URL；若启用代理，确认代理 token 未过期。
3. Admin 面板提示 “数据库未启用”：确保 `.env` 中配置了 `DATABASE_URL` 并运行 Alembic 迁移。
4. Sidebar 提示版本不一致：同步三处版本文件并重新 `npm run build`。
5. 前端静态站没更新：删除旧 `frontend/out`，重新运行 `npm run build` 并确认静态目录被部署。

## 11. 文档与协作
- 新增功能需在 README 或 `docs/` 中记录使用方式；涉及配置变更也要同步更新 `.env.example`。
- 若修改安全策略、版本策略或代理模式，请在 PR 中更新本文件并注明原因。
- 当前仓库不存在 `.cursor/rules` 或 `.github/copilot-instructions.md`；若未来添加需将关键规则摘录到本章节。

## 12. 提交前自检表
1. `ruff check`、`mypy`、`pytest` 是否全部通过？
2. `npm run lint`、`npm run build` 是否通过？
3. 新环境变量是否写入 `.env.example`、README、本文？
4. 涉及版本时，三处版本文件与 `CHANGELOG.md` 是否同步？
5. 是否完善日志、异常处理、fallback？
6. 是否存在临时代码/`TODO`？如未完成请转 issue，而非留在主干。

—— 若遇到指南未覆盖的情况，请在 Issue/PR 中记录，并在后续修改中补充进 AGENTS.md，保持知识同步。

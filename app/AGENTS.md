# 后端指南

## 概览
- `app/` 分层结构为 `api → services → models`，`core` 承载共享基础设施/配置。

## 目录结构
```text
app/
├── api/                # HTTP 路由契约（仅路由）
├── core/               # 全局配置、数据库连接、应用上下文、认证辅助
├── models/             # SQLAlchemy 实体与关系
├── services/           # 业务编排、提供商、外部客户端
├── gitea/              # Gitea 客户端集成 → 详见 app/gitea/AGENTS.md
└── review/             # 审查编排核心 → 详见 app/review/AGENTS.md
```

## 代码放置规则
| 变更类型 | 放置位置 | 说明 |
|----------|----------|------|
| 新增端点 | `app/api/routes.py` | 薄路由处理器；逻辑委托至 service |
| 新增业务流程 | `app/services/*.py` | 编排逻辑与策略 |
| 新增数据表/实体 | `app/models/*.py` | 包含关系定义，并在 `models/__init__.py` 中导出 |
| 新增环境变量 | `app/core/config.py` | 并在 `.env.example` 和 README 中补充说明 |
| 应用启动/中间件 | `app/main.py` | 仅上下文组装与中间件 |

## 分层边界
- **API 层**
  - 解析请求，返回响应。
  - 可执行认证/权限依赖注入。
  - 禁止内嵌多步骤业务逻辑。
- **Services 层**
  - 拥有工作流编排和外部 API 调用。
  - 统一使用 `DBService`/`AdminService` 或 `AsyncSession`。
- **Models 层**
  - 模式、关系、序列化辅助。
  - 不含编排逻辑。
- **Core 层**
  - 全局配置、数据库/会话工厂、应用上下文及共享认证辅助。

## 约定
- 写入操作使用 `AsyncSession` 并显式提交。
- 导入顺序：标准库 → 第三方 → 本地。
- 路由函数保持聚焦；将重复的权限/验证模式提取至 services/helpers。
- 服务命名应传达领域意图（如 `webhook_handler`、`admin_service`、`review_engine`）。
- 管理路由未拆分独立文件，全部位于 `app/api/routes.py`。

## 反模式
- 不得在路由处理器中放置跨域工作流逻辑。
- 不得在后端 API 之外的前端代码路径中访问数据库。
- 不得绕过 `admin_required(...)` 访问管理数据变更端点。
- 不得在 provider/client 错误中跳过 token 脱敏/安全日志。

## 验证（后端变更后）
```bash
uv run ruff check app
uv run mypy app
uv run pytest
```

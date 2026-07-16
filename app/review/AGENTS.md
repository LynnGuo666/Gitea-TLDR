# 审查编排指南

## 概览
- `app/review/` 是 PR 审查与 Issue 分析的编排核心，负责 webhook 事件处理、引擎调度、结果反馈。

## 目录结构
```text
review/
├── webhook_handler.py   # Webhook 事件入口（核心编排）
├── issue_service.py     # Issue 智能分析服务
├── engine.py            # 审查引擎调度（Provider 路由，默认 forge）
├── config_health.py     # 仓库配置健康检查
└── providers/           # 多引擎实现 → 详见 providers/AGENTS.md
```

## 代码定位
| 任务 | 位置 | 说明 |
|------|------|------|
| PR 创建/更新 webhook | `webhook_handler.py` | `handle_pull_request_event()` |
| PR 评论命令触发 | `webhook_handler.py` | `handle_comment_event()` — 解析 `/review` 命令 |
| Issue 评论命令触发 | `webhook_handler.py` | 路由至 `IssueAnalysisService` |
| 引擎选择与调度 | `engine.py` | `ReviewEngine` — 懒加载 + forge 兜底 |
| Issue 分析 | `issue_service.py` | 文本分析、分类、方案生成 |
| 配置健康检查 | `config_health.py` | 检查仓库 review/issue 配置状态 |

## 数据流
```
Gitea Webhook
    ↓
WebhookHandler.handle()
    ├── handle_pull_request_event() → ReviewEngine.analyze_pr() → Provider → PR 评论/审查
    ├── handle_comment_event() → 解析命令 → /review → ReviewEngine / /issue → IssueAnalysisService
    └── 审计日志 → AuditService
```

## 约定
- Webhook 处理器不直接调用 provider；通过 `ReviewEngine` 统一路由。
- 默认引擎为 `forge`；`claude_code` / `codex_cli` 为 legacy extras（`ENABLE_LEGACY_PROVIDERS=true` 才注册）。
- Issue 分析目前仅 Forge 引擎支持；其他引擎通过 `supports_issue()` 声明能力。
- 所有 webhook 入口需验证签名（`WEBHOOK_SECRET` 已配置时）。
- 审查结果通过 `ReviewResult` 标准化输出（summary + inline_comments + usage_metadata）。
- 所有 provider 调用前后由 webhook_handler 统一创建 / 收尾 `ProviderRun` 记录，无引擎特判。
- 处理过程中的错误保留可诊断信息，但必须脱敏 token/密钥。

## 反模式
- 不得在 `webhook_handler.py` 中直接添加新的 provider 调用逻辑；应通过 `ReviewEngine`。
- 不得跳过 webhook 签名验证。
- 不得在日志中泄露 Gitea token、API key 或用户凭证。
- 不得在 webhook 处理中执行耗时操作（如大文件下载）而不设置超时。
- Issue 分析前必须检查 provider 是否声明 `supports_issue()`。

# Gitea 客户端指南

## 概览
- `app/gitea/` 封装 Gitea API 交互，包括认证、仓库管理、权限查询、命令解析。

## 目录结构
```text
gitea/
├── client.py           # Gitea API 客户端（843 行）
├── auth.py             # 认证管理器（OAuth token 获取/刷新/验证）
├── repo_manager.py     # 仓库克隆与管理
├── repo_registry.py    # 仓库注册与查找
├── command_parser.py   # PR/Issue 评论命令解析（/review、/issue）
└── permission.py       # 权限查询
```

## 代码定位
| 任务 | 位置 | 说明 |
|------|------|------|
| Gitea API 调用 | `client.py` | REST API 封装：PR、Issue、评论、状态、文件 |
| OAuth 认证 | `auth.py` | Token 交换、刷新、用户信息、admin 状态 |
| 仓库克隆 | `repo_manager.py` | clone/pull、工作目录管理、token 安全处理 |
| 仓库注册 | `repo_registry.py` | 仓库发现与注册 |
| 命令解析 | `command_parser.py` | 解析 `/review --features`、`/issue --focus` |
| 权限查询 | `permission.py` | 仓库访问权限检查 |

## 约定
- 所有 Gitea API 调用必须通过 `GiteaClient`；禁止在其他模块直接构造 HTTP 请求。
- Token 在日志中必须脱敏；URL 中不得包含明文 token。
- 仓库克隆路径使用 `repo_manager.py` 统一管理；避免路径遍历漏洞。
- 命令解析需保持向后兼容；新增参数时保留旧参数别名。
- 认证失败时返回可操作的错误信息（如"token 过期，请重新授权"），而非裸 HTTP 状态码。

## 安全规则
- Token 通过 PyNaCl 加密存储（`auth.py`）；运行时解密后仅在内存中持有。
- 仓库克隆时 token 必须以环境变量方式注入 git 命令，不得出现在命令行参数中。
- 日志打印 API 响应前须过滤 `access_token`、`token`、`password` 等敏感字段。
- 权限检查采用 Fail-Closed 原则：未知状态视为无权限。

## 反模式
- 不得在其他模块中直接使用 `httpx` 或 `requests` 调用 Gitea API；必须通过 `GiteaClient`。
- 不得在日志、异常信息或 API 返回值中暴露 Gitea token。
- 不得在仓库克隆命令中拼接 token 到命令行；使用环境变量传递。
- 不得绕过 `AuthManager` 直接使用硬编码 token。

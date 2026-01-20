# 管理后台使用指南

## 概述

Gitea PR Reviewer v1.8.0 引入了全新的管理后台功能，提供系统监控、配置管理和用户管理等能力。

## 快速开始

### 1. 启用管理后台

在 `.env` 文件中配置：

```bash
# 启用管理后台（默认启用）
ADMIN_ENABLED=true

# 设置初始管理员用户名（必须与 Gitea 用户名一致）
INITIAL_ADMIN_USERNAME=admin

# Webhook 日志保留设置
WEBHOOK_LOG_RETENTION_DAYS=30
WEBHOOK_LOG_RETENTION_DAYS_FAILED=90
```

### 2. 启动应用

首次启动时，系统会自动创建初始管理员用户：

```bash
python app/main.py
# 或
docker compose up
```

日志中会显示：
```
初始化超级管理员: admin
管理后台已启用
管理后台路由已注册
```

### 3. 访问管理后台

1. 使用 Gitea OAuth 登录（用户名必须是 `INITIAL_ADMIN_USERNAME` 配置的值）
2. 登录成功后，侧边栏会显示"管理后台"入口
3. 点击进入 `/admin` 查看 Dashboard

## 功能模块

### Dashboard 看板 (`/admin`)

实时展示系统统计数据：

**审查次数**
- 总审查次数
- 今日、本周、本月审查次数

**Token 消耗**
- 总 Token 消耗
- 今日、本周、本月消耗趋势

**Webhook 统计**
- 总 Webhook 次数
- 今日触发次数
- 成功率

**仓库统计**
- 总仓库数
- 活跃仓库数

**快捷操作**
- 全局配置管理
- 仓库批量管理
- 审查历史查询
- Webhook 日志查看

### 管理员用户管理

#### 角色说明

**super_admin（超级管理员）**
- 拥有所有权限
- 可以创建、更新、删除其他管理员
- 可以修改所有配置

**admin（普通管理员）**
- 可以查看统计数据
- 可以查看日志和配置
- 只能修改自己的信息
- 权限可通过 `permissions` 字段自定义

#### API 端点

```bash
# 获取管理员列表
GET /api/admin/users?is_active=true

# 创建管理员（仅 super_admin）
POST /api/admin/users
{
  "username": "newadmin",
  "email": "admin@example.com",
  "role": "admin",
  "permissions": {
    "repos": ["read", "write"],
    "config": ["read"],
    "webhooks": ["read"]
  }
}

# 更新管理员
PUT /api/admin/users/newadmin
{
  "email": "new@example.com",
  "role": "super_admin",
  "is_active": true
}

# 删除管理员（仅 super_admin，不能删除自己）
DELETE /api/admin/users/newadmin
```

### 全局配置管理

#### 配置分类

**claude**（Claude 配置）
- `default_anthropic_base_url`: 默认 API Base URL
- `default_anthropic_auth_token`: 默认 API Key
- `default_model_name`: 默认模型名称
- `default_max_tokens`: 默认 token 限制
- `default_temperature`: 默认温度参数

**review**（审查配置）
- `default_review_focus`: 默认审查方向
- `default_webhook_events`: 默认监听事件
- `auto_request_reviewer`: 是否自动请求审查者
- `auto_invite_bot`: 是否自动邀请 Bot

**performance**（性能配置）
- `max_files_per_review`: 单次审查最大文件数
- `max_diff_size_bytes`: 单次审查最大 diff 大小
- `max_concurrent_reviews`: 最大并发审查数
- `api_rate_limit`: API 调用频率限制

**advanced**（高级配置）
- `claude_code_path`: Claude Code CLI 路径
- `work_dir`: 工作目录
- `log_retention_days`: 日志保留天数
- `enable_debug_mode`: 是否启用 Debug 模式

#### API 端点

```bash
# 获取所有配置
GET /api/admin/settings?category=claude

# 更新配置
PUT /api/admin/settings/default_model_name
{
  "value": "claude-3.5-sonnet",
  "category": "claude",
  "description": "默认使用的 Claude 模型"
}

# 删除配置
DELETE /api/admin/settings/some_key
```

### Webhook 日志查看

#### 日志字段

- `request_id`: 唯一请求 ID
- `repository_id`: 仓库 ID
- `event_type`: 事件类型（pull_request/issue_comment）
- `payload`: 完整的 Webhook Payload（JSON）
- `status`: 处理状态（success/error/retrying）
- `error_message`: 错误信息（如果失败）
- `processing_time_ms`: 处理耗时（毫秒）
- `retry_count`: 重试次数

#### API 端点

```bash
# 获取日志列表（支持分页、筛选）
GET /api/admin/webhooks/logs?repository_id=1&status=error&limit=50&offset=0

# 获取日志详情（包含完整 Payload）
GET /api/admin/webhooks/logs/123

# 日志自动清理
# 成功日志：保留 WEBHOOK_LOG_RETENTION_DAYS（默认 30 天）
# 失败日志：保留 WEBHOOK_LOG_RETENTION_DAYS_FAILED（默认 90 天）
```

## 权限控制

### 权限检查流程

1. 用户通过 OAuth 登录
2. 请求管理后台 API 时，中间件检查用户是否在 `admin_users` 表中
3. 根据用户角色和权限配置判断是否允许访问

### 权限配置示例

```json
{
  "repos": ["read", "write", "delete"],
  "config": ["read", "write"],
  "users": ["read"],
  "webhooks": ["read", "write"]
}
```

### 使用装饰器

```python
from app.core.admin_auth import admin_required
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/admin/sensitive")
async def get_sensitive_data(
    admin: AdminUser = Depends(admin_required("config", "read"))
):
    # 只有拥有 config.read 权限的管理员可以访问
    return {"data": "sensitive"}
```

## 数据库迁移

### 应用迁移

```bash
# 升级到最新版本
alembic upgrade head

# 查看当前版本
alembic current

# 查看迁移历史
alembic history
```

### 回滚（如需要）

```bash
# 回滚到上一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade <revision_id>
```

## 最佳实践

### 1. 管理员账号管理

- 定期审查管理员列表，移除不再需要的账号
- 为每个管理员设置合适的权限，遵循最小权限原则
- 保持至少一个 super_admin 账号active

### 2. 日志管理

- 根据存储空间调整日志保留时间
- 定期检查失败日志，及时发现系统问题
- 对于重要的失败日志，可以手动导出保存

### 3. 配置管理

- 修改全局配置前先备份当前配置
- 重要配置更改后及时测试
- 使用配置的 description 字段记录变更原因

### 4. 安全建议

- 不要将 `INITIAL_ADMIN_USERNAME` 设置为常见用户名（如 admin, root）
- 定期更新管理员邮箱，确保能接收系统通知
- 使用 OAuth 登录时，确保 Gitea 账号安全

## 故障排查

### 无法访问管理后台

**问题**: 侧边栏没有"管理后台"入口

**解决**:
1. 检查 `.env` 中 `ADMIN_ENABLED=true`
2. 确认已使用正确的用户名登录
3. 检查数据库中是否有该用户：
   ```sql
   SELECT * FROM admin_users WHERE username = 'your_username';
   ```

### Dashboard 无数据

**问题**: Dashboard 统计数据为 0

**解决**:
1. 确认数据库中有审查记录：`SELECT COUNT(*) FROM review_sessions;`
2. 检查数据库连接是否正常
3. 查看应用日志是否有错误

### 权限错误

**问题**: 返回 403 Forbidden

**解决**:
1. 确认用户角色和权限配置
2. 检查 API 端点需要的权限等级
3. super_admin 拥有所有权限，可以先升级为 super_admin 测试

## 未来规划

管理后台后续版本将支持：

- **仓库批量管理**: 批量启用/禁用 Webhook，批量设置配置
- **审查历史查询**: 高级筛选、导出、生成报告
- **API Key 池管理**: 多 Key 轮换、配额监控、自动切换
- **实时监控**: WebSocket 推送实时事件
- **审查质量分析**: 问题分类统计、趋势图表、仓库排行

## 支持

如有问题，请：
1. 查看日志文件：`tail -f /path/to/logs`
2. 检查数据库状态：`sqlite3 /tmp/gitea-pr-reviewer/gitea_pr_reviewer.db`
3. 提交 Issue: https://github.com/your-org/gitea-pr-reviewer/issues

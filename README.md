# Gitea PR Reviewer

基于Claude Code的Gitea Pull Request自动审查工具。当用户提交PR后，该工具会自动接收webhook通知，使用Claude Code分析代码变更，并将审查结果反馈到Gitea。

## 功能特性

- **自动化审查**：接收Gitea webhook，自动触发PR代码审查
- **手动触发**：通过评论 `/review` 命令手动触发审查
- **完整上下文分析**：克隆完整代码库，提供完整上下文给Claude Code
- **灵活的反馈机制**：通过HTTP标头或命令参数控制审查功能
  - PR评论（Comment）
  - PR审查（Review）
  - 提交状态（Status）
- **多维度审查**：
  - 代码质量和最佳实践
  - 安全漏洞检测
  - 性能问题分析
  - 逻辑错误和bug发现
- **异步处理**：立即返回202响应，后台处理审查任务，避免webhook超时

## 技术栈

- **FastAPI**：高性能异步Web框架
- **Next.js 静态导出**：构建 `/ui` 前端控制台
- **Claude Code CLI**：代码分析引擎
- **httpx**：异步HTTP客户端
- **Pydantic**：配置管理和数据验证

## 项目结构

```
gitea-tldr/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── config.py            # 配置管理
│   ├── version.py           # 版本信息管理
│   ├── gitea_client.py      # Gitea API客户端
│   ├── repo_manager.py      # 代码库克隆和管理
│   ├── claude_analyzer.py   # Claude Code CLI调用
│   ├── webhook_handler.py   # Webhook处理逻辑
│   └── command_parser.py    # 命令解析器（手动触发）
├── requirements.txt
├── .env.example
├── README.md
└── CHANGELOG.md             # 更新日志
```

## 安装部署

### 1. 环境要求

- Python 3.11+
- Git
- Claude Code CLI（已安装并配置）

### 2. 安装依赖

```bash
# 克隆仓库
git clone <repository-url>
cd gitea-pr-reviewer

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# Gitea配置
GITEA_URL=https://gitea.example.com
GITEA_TOKEN=your_gitea_access_token_here

# Webhook配置（可选，用于验证webhook请求）
WEBHOOK_SECRET=your_webhook_secret_here

# Claude Code配置
CLAUDE_CODE_PATH=claude

# 工作目录配置
WORK_DIR=/tmp/gitea-pr-reviewer

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 日志配置
LOG_LEVEL=INFO

# Debug模式（可选，开启详细日志）
DEBUG=false

# Bot配置（可选，用于手动触发功能）
BOT_USERNAME=pr-reviewer-bot

# OAuth（可选，用于用户登录）
OAUTH_CLIENT_ID=
OAUTH_CLIENT_SECRET=
OAUTH_REDIRECT_URL=http://localhost:8000/api/auth/callback
# 逗号分隔的scope列表
OAUTH_SCOPES=read:user,read:repository
SESSION_COOKIE_NAME=gitea_session
SESSION_COOKIE_SECURE=false
```

### 4. 启动服务

```bash
# 开发模式
python -m app.main

# 或使用uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端控制台位于 `frontend` 目录，可通过 Next.js 静态导出后与 FastAPI 一并托管：

```bash
cd frontend
npm install
npm run build  # 生成 out/ 目录
```

如果检测到 `frontend/out`，FastAPI 将自动在 `/ui` 路径挂载静态资源。

### 5. 配置Gitea Webhook

在Gitea仓库设置中添加Webhook：

1. 进入仓库 → 设置 → Webhooks → 添加Webhook
2. 配置参数：
   - **URL**: `http://your-server:8000/webhook`
   - **HTTP方法**: POST
   - **内容类型**: application/json
   - **密钥**（可选）: 与 `.env` 中的 `WEBHOOK_SECRET` 一致
   - **触发事件**:
     - ✅ 选择 "Pull Request"（用于自动触发）
     - ✅ 选择 "Issue Comment"（用于手动触发）
   - **自定义标头**（可选，仅用于自动触发）:
     - `X-Review-Features: comment,review,status`
     - `X-Review-Focus: quality,security,performance,logic`

## 使用说明

### 1. 自动触发（Webhook）

当PR被创建或更新时，工具会自动触发审查。

### 2. 手动触发（评论命令）

在PR评论中使用 `/review` 命令可以手动触发审查：

#### 基本用法

```
/review
```

如果配置了 `BOT_USERNAME`，需要@bot：

```
@pr-reviewer-bot /review
```

#### 高级用法

指定审查功能：

```
@pr-reviewer-bot /review --features comment,status
```

指定审查重点：

```
@pr-reviewer-bot /review --focus security,performance
```

完整示例：

```
@pr-reviewer-bot /review --features comment,review,status --focus security,quality
```

#### 命令参数说明

- `--features`: 指定启用的功能（comment, review, status）
  - 默认值：`comment`

- `--focus`: 指定审查重点（quality, security, performance, logic）
  - 默认值：`quality,security,performance,logic`

### Webhook标头配置

### 使用 OAuth 登录（可选）

若希望前端用户使用自己的 Gitea 账号登录并下发仓库访问权限，需要在 Gitea 中创建 OAuth2 Application，并填写上文的 `OAUTH_*` 配置：

1. 在 Gitea `Settings → Applications → Manage OAuth2 Applications` 中创建应用，记录 **Client ID** / **Client Secret**，并将 Redirect URL 指向 `http(s)://your-server/api/auth/callback`。
2. 确保 Gitea OAuth 授权端点为 `https://<gitea>/login/oauth/authorize`，令牌端点为 `https://<gitea>/login/oauth/access_token`（参考官方文档: https://docs.gitea.com/development/oauth2-provider ）。
3. 将得到的 Client 信息写入 `.env`，并按需调整 `OAUTH_SCOPES`（默认申请 `read:user`、`read:repository`）。
4. 重启服务后，前端侧边栏会出现 “连接 Gitea” 按钮；登录完成后，仓库列表及 Webhook 配置均将使用用户自身的访问令牌调用 Gitea API。

通过自定义HTTP标头控制审查行为：

#### X-Review-Features

控制启用的功能，多个功能用逗号分隔：

- `comment`: 在PR中发布评论
- `review`: 创建PR审查
- `status`: 设置提交状态

示例：
```
X-Review-Features: comment,review,status
```

如果不设置此标头，默认只启用 `comment`。

#### X-Review-Focus

控制审查重点，多个重点用逗号分隔：

- `quality`: 代码质量和最佳实践
- `security`: 安全漏洞检测
- `performance`: 性能问题分析
- `logic`: 逻辑错误和bug

示例：
```
X-Review-Focus: security,performance
```

如果不设置此标头，默认启用所有审查重点。

### API端点

#### GET /

健康检查端点，返回服务状态和版本信息

```bash
curl http://localhost:8000/
```

响应示例：
```json
{
  "status": "ok",
  "service": "Gitea PR Reviewer",
  "version": "1.0.0"
}
```

#### GET /health

健康检查端点

```bash
curl http://localhost:8000/health
```

#### GET /version

查询版本信息和当前版本更新日志

```bash
curl http://localhost:8000/version
```

响应示例：
```json
{
  "version": "1.0.0",
  "info": "Gitea PR Reviewer v1.0.0 (2025-11-28)",
  "changelog": "..."
}
```

#### GET /changelog

查询完整更新日志

```bash
curl http://localhost:8000/changelog
```

#### POST /webhook

Gitea Webhook接收端点

请求标头：
- `X-Gitea-Signature`: Webhook签名（如果配置了密钥）
- `X-Gitea-Event`: 事件类型（`pull_request` 或 `issue_comment`）
- `X-Review-Features`: 审查功能配置（可选，仅用于PR事件）
- `X-Review-Focus`: 审查重点配置（可选，仅用于PR事件）

## 工作流程

### 自动触发流程

1. 用户在Gitea中创建或更新PR
2. Gitea发送 `pull_request` webhook到本服务
3. 服务验证webhook签名（如果配置）
4. 解析标头获取功能和重点配置
5. 返回202响应，启动后台任务
6. 后台任务执行：
   - 设置初始状态（如果启用）
   - 获取PR diff
   - 克隆完整代码库
   - 调用Claude Code分析
   - 根据配置发布评论/审查/状态
   - 清理临时文件
7. 审查结果显示在Gitea PR页面

### 手动触发流程

1. 用户在PR评论中输入 `/review` 命令（可能需要@bot）
2. Gitea发送 `issue_comment` webhook到本服务
3. 服务解析评论内容，识别命令和参数
4. 如果是有效命令，返回202响应，启动后台任务
5. 后台任务执行（与自动触发相同）
6. 审查结果显示在Gitea PR页面

## 生产部署建议

### 使用systemd服务

创建 `/etc/systemd/system/gitea-pr-reviewer.service`：

```ini
[Unit]
Description=Gitea PR Reviewer
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/gitea-pr-reviewer
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable gitea-pr-reviewer
sudo systemctl start gitea-pr-reviewer
```

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name pr-reviewer.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 使用Docker部署

项目已包含完整的Docker支持，Claude Code CLI已打包在镜像中。

#### 方式1：使用Docker Compose（推荐）

Docker Compose 会自动从 `.env` 文件读取所有环境变量，无需在 `docker-compose.yml` 中逐个配置。

1. 创建并配置 `.env` 文件：

```bash
cp .env.example .env
# 编辑 .env 文件，填写所有必需的配置项
# 重要：确保配置了以下关键变量
# - GITEA_URL
# - GITEA_TOKEN
# - OAUTH_CLIENT_ID (如果使用OAuth登录)
# - OAUTH_CLIENT_SECRET (如果使用OAuth登录)
# - OAUTH_REDIRECT_URL (如果使用OAuth登录)
# - ANTHROPIC_AUTH_TOKEN (如果使用Claude Code)
```

2. 启动服务：

```bash
docker compose up -d --build
```

3. 验证配置加载（可选）：

```bash
# 检查环境变量是否正确加载
docker compose config | grep -A 20 environment

# 在容器内验证OAuth配置
docker exec gitea-pr-reviewer python -c "
from app.core.config import settings
from app.services.auth_manager import AuthManager
print(f'OAuth enabled: {AuthManager().enabled}')
"
```

4. 查看日志：

```bash
docker compose logs -f
```

5. 停止服务：

```bash
docker compose down
```

**注意事项：**
- `.env` 文件包含敏感信息（如token和密钥），请勿提交到版本控制系统
- 修改 `.env` 后需要重启容器：`docker compose restart`
- 如需使用不同的配置文件，可以通过 `--env-file` 参数指定：
  ```bash
  docker compose --env-file .env.production up -d
  ```

#### 方式2：使用Docker命令

推荐使用 `--env-file` 参数从 `.env` 文件加载所有配置：

```bash
# 构建镜像
docker build -t gitea-pr-reviewer .

# 使用 .env 文件运行容器（推荐）
docker run -d \
  --name gitea-pr-reviewer \
  -p 8000:8000 \
  --env-file .env \
  -v pr-reviewer-data:/tmp/gitea-pr-reviewer \
  -v ./frontend:/app/frontend \
  gitea-pr-reviewer
```

或者手动指定每个环境变量：

```bash
docker run -d \
  --name gitea-pr-reviewer \
  -p 8000:8000 \
  -e GITEA_URL=https://gitea.example.com \
  -e GITEA_TOKEN=your_token \
  -e OAUTH_CLIENT_ID=your_client_id \
  -e OAUTH_CLIENT_SECRET=your_client_secret \
  -e OAUTH_REDIRECT_URL=http://localhost:8000/api/auth/callback \
  -e ANTHROPIC_BASE_URL=https://api.anthropic.com \
  -e ANTHROPIC_AUTH_TOKEN=your_anthropic_token \
  -e WEBHOOK_SECRET=your_secret \
  gitea-pr-reviewer
```

#### 方式3：使用GitHub Container Registry

项目配置了GitHub Actions自动构建，可以直接拉取镜像：

```bash
# 拉取最新镜像
docker pull ghcr.io/your-username/gitea-tldr:latest

# 运行（推荐使用.env文件）
docker run -d \
  --name gitea-pr-reviewer \
  -p 8000:8000 \
  --env-file .env \
  ghcr.io/your-username/gitea-tldr:latest

# 或直接指定环境变量
docker run -d \
  --name gitea-pr-reviewer \
  -p 8000:8000 \
  -e GITEA_URL=https://gitea.example.com \
  -e GITEA_TOKEN=your_token \
  -e ANTHROPIC_BASE_URL=https://api.anthropic.com \
  -e ANTHROPIC_AUTH_TOKEN=your_anthropic_token \
  ghcr.io/your-username/gitea-tldr:latest
```

#### Docker镜像特性

- 基于 `python:3.11-slim`
- 已预装 Node.js 20.x 和 npm
- 已预装 Claude Code CLI（通过npm安装）
- 支持 `linux/amd64` 和 `linux/arm64` 架构
- 包含健康检查
- 自动重启策略

## 故障排查

### 查看版本信息

```bash
# 方式1：访问API端点
curl http://localhost:8000/version

# 方式2：查看启动日志
# 服务启动时会打印版本横幅
```

### Claude Code调用失败

- 确认Claude Code CLI已正确安装：`claude --version`
- 检查 `CLAUDE_CODE_PATH` 配置是否正确
- 查看日志中的详细错误信息

### 仓库克隆失败

- 确认Gitea token有足够的权限
- 检查网络连接
- 确认工作目录有足够的磁盘空间

### Webhook未触发

- 检查Gitea webhook配置是否正确
- 确认服务器端口可访问
- 查看Gitea webhook日志

## 开发

### 运行测试

```bash
# TODO: 添加测试
pytest
```

### 代码格式化

```bash
black app/
isort app/
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请提交Issue。

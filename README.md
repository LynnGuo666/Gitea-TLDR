# Gitea PR Reviewer

基于Claude Code的Gitea Pull Request自动审查工具。当用户提交PR后，该工具会自动接收webhook通知，使用Claude Code分析代码变更，并将审查结果反馈到Gitea。

## 功能特性

- **自动化审查**：接收Gitea webhook，自动触发PR代码审查
- **完整上下文分析**：克隆完整代码库，提供完整上下文给Claude Code
- **灵活的反馈机制**：通过HTTP标头控制审查功能
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
│   ├── gitea_client.py      # Gitea API客户端
│   ├── repo_manager.py      # 代码库克隆和管理
│   ├── claude_analyzer.py   # Claude Code CLI调用
│   └── webhook_handler.py   # Webhook处理逻辑
├── requirements.txt
├── .env.example
└── README.md
```

## 安装部署

### 1. 环境要求

- Python 3.9+
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
```

### 4. 启动服务

```bash
# 开发模式
python -m app.main

# 或使用uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 配置Gitea Webhook

在Gitea仓库设置中添加Webhook：

1. 进入仓库 → 设置 → Webhooks → 添加Webhook
2. 配置参数：
   - **URL**: `http://your-server:8000/webhook`
   - **HTTP方法**: POST
   - **内容类型**: application/json
   - **密钥**（可选）: 与 `.env` 中的 `WEBHOOK_SECRET` 一致
   - **触发事件**: 选择 "Pull Request"
   - **自定义标头**（可选）:
     - `X-Review-Features: comment,review,status`
     - `X-Review-Focus: quality,security,performance,logic`

## 使用说明

### Webhook标头配置

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

健康检查端点

```bash
curl http://localhost:8000/
```

#### GET /health

健康检查端点

```bash
curl http://localhost:8000/health
```

#### POST /webhook

Gitea Webhook接收端点

请求标头：
- `X-Gitea-Signature`: Webhook签名（如果配置了密钥）
- `X-Gitea-Event`: 事件类型（应为 `pull_request`）
- `X-Review-Features`: 审查功能配置（可选）
- `X-Review-Focus`: 审查重点配置（可选）

## 工作流程

1. 用户在Gitea中创建或更新PR
2. Gitea发送webhook到本服务
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

1. 创建 `.env` 文件：

```bash
cp .env.example .env
# 编辑.env文件填写配置
```

2. 启动服务：

```bash
docker-compose up -d
```

3. 查看日志：

```bash
docker-compose logs -f
```

4. 停止服务：

```bash
docker-compose down
```

#### 方式2：使用Docker命令

```bash
# 构建镜像
docker build -t gitea-pr-reviewer .

# 运行容器
docker run -d \
  --name gitea-pr-reviewer \
  -p 8000:8000 \
  -e GITEA_URL=https://gitea.example.com \
  -e GITEA_TOKEN=your_token \
  -e WEBHOOK_SECRET=your_secret \
  gitea-pr-reviewer
```

#### 方式3：使用GitHub Container Registry

项目配置了GitHub Actions自动构建，可以直接拉取镜像：

```bash
# 拉取最新镜像
docker pull ghcr.io/your-username/gitea-tldr:latest

# 运行
docker run -d \
  --name gitea-pr-reviewer \
  -p 8000:8000 \
  --env-file .env \
  ghcr.io/your-username/gitea-tldr:latest
```

#### Docker镜像特性

- 基于 `python:3.11-slim`
- 已预装 Claude Code CLI
- 支持 `linux/amd64` 和 `linux/arm64` 架构
- 包含健康检查
- 自动重启策略

## 故障排查

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

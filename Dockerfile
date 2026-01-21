FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖和Node.js
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 验证Node.js和npm安装
RUN node --version && npm --version

# 使用npm全局安装Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# 验证Claude Code安装
RUN claude --version

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 复制 Alembic 配置和迁移文件
COPY alembic.ini ./
COPY alembic/ ./alembic/

# 复制启动脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 创建工作目录
RUN mkdir -p /tmp/gitea-pr-reviewer

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
ENTRYPOINT ["/docker-entrypoint.sh"]

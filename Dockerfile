FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装Claude Code CLI
# 注意：实际安装方式可能需要根据Claude Code的官方文档调整
RUN curl -fsSL https://claude.ai/install.sh | sh || \
    (echo "Claude Code安装失败，请检查安装脚本" && exit 1)

# 确保claude在PATH中
ENV PATH="/root/.local/bin:${PATH}"

# 验证Claude Code安装
RUN claude --version || echo "警告：Claude Code未正确安装"

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/

# 创建工作目录
RUN mkdir -p /tmp/gitea-pr-reviewer

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

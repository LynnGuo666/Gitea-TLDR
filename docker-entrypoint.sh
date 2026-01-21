#!/bin/bash
set -e

echo "=========================================="
echo "Gitea PR Reviewer - 启动脚本"
echo "=========================================="

# 等待工作目录就绪
mkdir -p "${WORK_DIR:-/tmp/gitea-pr-reviewer}"

# 运行数据库迁移
echo "正在运行数据库迁移..."
if [ -f "/app/alembic.ini" ]; then
    cd /app
    # 使用 Python 的 alembic 命令行工具运行迁移
    python -m alembic upgrade head
    echo "数据库迁移完成"
else
    echo "警告: 未找到 alembic.ini，跳过迁移"
fi

echo "=========================================="
echo "启动应用服务..."
echo "=========================================="

# 启动应用
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"

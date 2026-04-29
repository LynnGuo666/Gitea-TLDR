#!/bin/bash
set -e

echo "=========================================="
echo "LCPU AI Reviewer - 启动脚本"
echo "=========================================="

WORK_DIR="${WORK_DIR:-/app/review-workspace}"

# 以 root 启动时：修复工作目录属主后降权到 appuser 重新执行
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$WORK_DIR"
    chown -R 1000:1000 "$WORK_DIR"
    exec gosu 1000 "$0" "$@"
fi

# 等待工作目录就绪
mkdir -p "$WORK_DIR"

# 运行数据库迁移
echo "正在运行数据库迁移..."
if [ -f "/app/alembic.ini" ]; then
    cd /app
    python -m alembic upgrade head
    echo "数据库迁移完成"
else
    echo "警告: 未找到 alembic.ini，跳过迁移"
fi

echo "=========================================="
echo "启动应用服务..."
echo "=========================================="

exec uvicorn app.main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}" \
  --log-level "$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')" \
  --timeout-keep-alive "${KEEP_ALIVE:-60}"

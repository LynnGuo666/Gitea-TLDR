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
    # 容错：曾升级到 v2.3.0(0003) 又 revert 的环境，alembic_version 仍是 0003，
    # 但 0003 迁移文件已删除，`alembic upgrade head` 会报
    # `Can't locate revision identified by '0003'`。
    # 检测到此错误时用 `stamp --purge` 清空版本表后重新 stamp 到 0002
    #（最新保留的迁移点，0004 会随后由 upgrade 补上），再重试一次。
    if ! python -m alembic upgrade head 2>/tmp/alembic_upgrade.err; then
        if grep -q "Can't locate revision" /tmp/alembic_upgrade.err; then
            echo "检测到 alembic 版本指向已删除的迁移，自动 stamp 到 0002 后重试..."
            python -m alembic stamp 0002 --purge
            python -m alembic upgrade head
        else
            echo "数据库迁移失败：" >&2
            cat /tmp/alembic_upgrade.err >&2
            exit 1
        fi
    fi
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

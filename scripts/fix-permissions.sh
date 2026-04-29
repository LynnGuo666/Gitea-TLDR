#!/usr/bin/env bash
set -euo pipefail

WORK_DIR="${WORK_DIR:-./review-workspace}"
CONTAINER_UID="${CONTAINER_UID:-1000}"

echo "修复 $WORK_DIR 权限为 $CONTAINER_UID:$CONTAINER_UID ..."
sudo chown -R "${CONTAINER_UID}:${CONTAINER_UID}" "$WORK_DIR"
echo "完成。请重启容器：docker compose restart"

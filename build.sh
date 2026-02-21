#!/bin/bash

# 构建脚本

set -e

echo "开始构建 LCPU AI Reviewer Docker 镜像..."

# 获取版本号（如果有git tag）
VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "dev")
echo "版本: $VERSION"

# 构建镜像
docker build \
  --build-arg VERSION=$VERSION \
  -t gitea-pr-reviewer:$VERSION \
  -t gitea-pr-reviewer:latest \
  .

echo "构建完成！"
echo ""
echo "运行镜像："
echo "  docker run -d -p 8000:8000 --env-file .env gitea-pr-reviewer:latest"
echo ""
echo "或使用 docker-compose："
echo "  docker-compose up -d"

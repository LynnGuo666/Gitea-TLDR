# ---- Frontend builder ----
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---- Runtime（默认 target，不含 legacy CLI） ----
# 仅 Forge 引擎；claude_code / codex_cli legacy provider 需要的 nodejs + CLI
# 不进入默认镜像。需要 legacy 时构建 runtime-with-legacy target：
#   docker build -f docker/Dockerfile --target runtime-with-legacy -t gitea-tldr:legacy .
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/

COPY --from=frontend-builder /frontend/out ./frontend/out

COPY docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

RUN groupadd -r appuser && useradd -r -g appuser -u 1000 -d /app appuser \
    && chown -R appuser:appuser /app

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]


# ---- Runtime with legacy CLI（可选 target） ----
# 在 runtime 基础上追加 nodejs 20 runtime + claude-code / codex CLI 全局安装，
# 供 ENABLE_LEGACY_PROVIDERS=true 时 claude_code / codex_cli provider 调用。
# 默认 runtime target 不含这些二进制，镜像显著更小。
FROM runtime AS runtime-with-legacy

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /etc/apt/sources.list.d/nodesource.list /etc/apt/keyrings/nodesource.gpg \
    && npm install -g @anthropic-ai/claude-code @openai/codex \
    && claude --version

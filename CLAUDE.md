## Core Instruction for CodeX MCP

在任何时刻，你必须思考当前过程可以如何与codex进行协作，如何调用Codex 为你提供的MCP工具作为你客观全面分析的保障。
其中你**务必执行**以下几个步骤：
**1** 在你对用户需求形成初步分析后，将用户需求、初始思路告知codex，并要求其完善需求分析和实施计划。
**2** 在实施具体编码任务前，**必须向codex索要代码实现原型（要求codex仅给出unified diff patch，严禁对代码做任何真实修改）**。在获取代码原型后，你**只能以此为逻辑参考，再次对代码修改进行重写**，形成企业生产级别、可读性极高、可维护性极高的代码后，才能实施具体编程修改任务。
**3** 无论何时，只要完成切实编码行为后，**必须立即使用codex review代码改动和对应需求完成程度**。
**4** codex只能给出参考，你**必须有自己的思考，甚至需要对codex的回答提出置疑**。尽信书则不如无书，你与codex的最终使命都是达成统一、全面、精准的意见，所以你们必须不断争辩已找到通向真理的唯一途径。


## Codex Tool Invocation Specification

 1. 工具概述

  codex MCP 提供了一个工具 `codex`，用于执行 AI 辅助的编码任务。该工具**通过 MCP 协议调用**，无需使用命令行。

  2. 工具参数

  **必选**参数：
  - PROMPT (string): 发送给 codex 的任务指令
  - cd (Path): codex 执行任务的工作目录根路径

  可选参数：
  - sandbox (string): 沙箱策略，可选值：
    - "read-only" (默认): 只读模式，最安全
    - "workspace-write": 允许在工作区写入
    - "danger-full-access": 完全访问权限
  - SESSION_ID (UUID | null): 用于继续之前的会话以与codex进行多轮交互，默认为 None（开启新会话）
  - skip_git_repo_check (boolean): 是否允许在非 Git 仓库中运行，默认 False
  - return_all_messages (boolean): 是否返回所有消息（包括推理、工具调用等），默认 False

  返回值：
  {
    "success": true,
    "SESSION_ID": "uuid-string",
    "agent_messages": "agent回复的文本内容",
    "all_messages": []  // 仅当 return_all_messages=True 时包含
  }
  或失败时：
  {
    "success": false,
    "error": "错误信息"
  }

  3. 使用方式

  开启新对话：
  - 不传 SESSION_ID 参数（或传 None）
  - 工具会返回新的 SESSION_ID 用于后续对话

  继续之前的对话：
  - 将之前返回的 SESSION_ID 作为参数传入
  - 同一会话的上下文会被保留

  4. 调用规范

  **必须遵守**：
  - 每次调用 codex 工具时，必须保存返回的 SESSION_ID，以便后续继续对话
  - cd 参数必须指向存在的目录，否则工具会静默失败
  - 严禁codex对代码进行实际修改，使用 sandbox="read-only" 以避免意外，并要求codex仅给出unified diff patch即可

  推荐用法：
  - 如需详细追踪 codex 的推理过程和工具调用，设置 return_all_messages=True
  - 对于精准定位、debug、代码原型快速编写等任务，优先使用 codex 工具

  5. 注意事项

  - 会话管理：始终追踪 SESSION_ID，避免会话混乱
  - 工作目录：确保 cd 参数指向正确且存在的目录
  - 错误处理：检查返回值的 success 字段，处理可能的错误
  
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gitea PR Reviewer is an automated code review tool that uses Claude Code CLI to analyze pull requests in Gitea. It supports both automatic webhook-triggered reviews and manual command-based reviews.

## Development Setup

### Initial Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Running the Service

```bash
# Development mode with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or run directly
python -m app.main
```

### Docker Development

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after changes
docker-compose build
```

## Architecture Overview

### Request Flow

**Automatic Trigger (Webhook):**
1. `main.py` receives `pull_request` webhook → returns 202 immediately
2. Background task → `webhook_handler.handle_pull_request()`
3. Extracts features/focus from HTTP headers (`X-Review-Features`, `X-Review-Focus`)
4. Calls `_perform_review()` with configuration

**Manual Trigger (Comment):**
1. `main.py` receives `issue_comment` webhook → returns 202 immediately
2. Background task → `webhook_handler.handle_issue_comment()`
3. `command_parser` parses `/review` command and extracts `--features`/`--focus` parameters
4. Validates it's a PR comment (checks `issue.pull_request` exists)
5. Calls `_perform_review()` with parsed configuration

### Core Review Flow (`_perform_review`)

This is the shared logic for both triggers:

1. **Setup**: Create initial comment/status (if enabled)
2. **Fetch**: Get PR diff via `gitea_client.get_pull_request_diff()`
3. **Clone**: Clone repository to temp directory via `repo_manager.clone_repository()`
   - Falls back to simple mode if clone fails
4. **Analyze**:
   - Full mode: `claude_analyzer.analyze_pr()` - passes diff via stdin to `claude -p <prompt>`
   - Simple mode: `claude_analyzer.analyze_pr_simple()` - only analyzes diff without repo context
5. **Publish**: Post results based on features:
   - `comment`: Update/create PR comment
   - `review`: Create PR review
   - `status`: Set commit status
6. **Cleanup**: Remove cloned repository

### Module Responsibilities

- **`gitea_client.py`**: All Gitea API interactions (get PR, create comment/review/status)
  - Debug mode logs all requests/responses
  - Uses httpx for async HTTP

- **`repo_manager.py`**: Clone and manage temporary git repositories
  - Clones to `WORK_DIR/{owner}_{repo}_pr{number}`
  - Auto-cleanup after analysis

- **`claude_analyzer.py`**: Invoke Claude Code CLI
  - Uses `claude -p <prompt> --output-format text` with diff piped to stdin
  - Supports both full (with repo context) and simple (diff-only) modes
  - `_build_review_prompt()` constructs prompt from focus areas and PR metadata

- **`command_parser.py`**: Parse `/review` commands from PR comments
  - `ReviewCommand` dataclass: stores command, features, focus_areas
  - Supports `--features` and `--focus` arguments
  - Optional `@bot_username` validation

- **`webhook_handler.py`**: Orchestrate review workflow
  - `handle_pull_request()`: Process PR webhooks (actions: opened, synchronized)
  - `handle_issue_comment()`: Process comment webhooks (action: created)
  - `_perform_review()`: **Shared core logic** for both trigger types
  - `parse_review_features()/parse_review_focus()`: Parse HTTP headers for auto-trigger

- **`version.py`**: Version management
  - `__version__`, `__release_date__` constants
  - `get_version_banner()`: ASCII art banner shown on startup
  - `VERSION_HISTORY`: Dict storing changelog for each version

## Configuration System

All config in `app/config.py` using Pydantic settings. Environment variables loaded from `.env`:

**Required:**
- `GITEA_URL`: Gitea server URL
- `GITEA_TOKEN`: Access token for API

**Optional but recommended:**
- `WEBHOOK_SECRET`: HMAC signature validation
- `BOT_USERNAME`: Required for manual trigger with @ mentions
- `DEBUG`: Set to `true` for verbose logging (all API calls, webhooks, Claude I/O)

**Defaults:**
- `CLAUDE_CODE_PATH=claude`: CLI binary name/path
- `WORK_DIR=/tmp/gitea-pr-reviewer`: Temp clone directory
- `LOG_LEVEL=INFO`

## Feature Configuration

Both triggers support the same feature set:

### Features (what feedback to provide)
- `comment`: Create/update PR comment with review results
- `review`: Create official PR review
- `status`: Set commit status (success/failure based on severity)

### Focus Areas (what to review)
- `quality`: Code quality, best practices
- `security`: Security vulnerabilities (SQL injection, XSS, etc.)
- `performance`: Performance issues
- `logic`: Logic errors, bugs

**Defaults:**
- Auto-trigger: `features=["comment"]`, `focus=all`
- Manual trigger: Same, unless specified in command

## Debug Mode

Enable with `DEBUG=true`:
- Logs prefixed with `[API请求]`, `[响应体]`, `[Webhook Payload]`, `[Claude Prompt]`, `[Claude Response]`
- All Gitea API requests/responses logged by `gitea_client._log_debug()/_log_response()`
- Full webhook payloads logged in `main.py`
- Claude prompts and responses logged in `claude_analyzer.py`

## Version Management

**IMPORTANT**: Every time you modify code, you MUST update the version number and changelog.

When releasing new versions:

1. Update `app/version.py`:
   ```python
   __version__ = "1.1.0"
   __release_date__ = "2025-12-XX"

   VERSION_HISTORY = {
       "1.1.0": {"date": "...", "changes": [...]},
       "1.0.0": {...}  # keep old versions
   }
   ```
   - Do NOT use emojis in version history changes
   - Use simple text descriptions like "新增：...", "优化：...", "修复：..."

2. Update `CHANGELOG.md` with new entry at top
   - Add new version section at the beginning
   - Do NOT use emojis (no ✨, 🔧, ⚙️, etc.)
   - Use plain text with prefixes: "新增功能", "技术改进", "问题修复"
   - Follow semantic versioning:
     - Major (X.0.0): Breaking changes
     - Minor (0.X.0): New features, backwards compatible
     - Patch (0.0.X): Bug fixes, backwards compatible

3. Version appears in:
   - Startup banner (ASCII art)
   - `GET /` response
   - `GET /version` response
   - FastAPI docs

## Claude Code CLI Integration

**Critical implementation details:**

The project calls Claude Code CLI to analyze PR diffs. The correct calling pattern is:

```bash
echo "$diff_content" | claude -p "$prompt" --output-format text
```

**In code (`claude_analyzer.py`):**
- Prompt built in `_build_review_prompt(focus_areas, pr_info)` - does NOT include diff
- Diff passed via stdin: `process.communicate(input=diff_content.encode('utf-8'))`
- Uses `-p` flag (not `--message`)
- Includes `--output-format text` for plain text output
- When repo cloned: `cwd=str(repo_path)` to give Claude full context

**Two analysis modes:**
1. `analyze_pr()`: With full repo clone (preferred)
2. `analyze_pr_simple()`: Fallback with only diff (no repo context)

## Testing Manual Trigger

```bash
# In PR comment on Gitea:
/review

# With bot username:
@pr-reviewer-bot /review

# With options:
@pr-reviewer-bot /review --features comment,status --focus security,performance
```

Command parser regex patterns in `command_parser.py`:
- `--features\s+(\S+)` → splits on comma
- `--focus\s+(\S+)` → splits on comma

## API Endpoints

- `GET /`: Health + version info
- `GET /health`: Health check
- `GET /version`: Current version + changelog
- `GET /changelog`: Full version history
- `POST /webhook`: Webhook receiver
  - Handles `X-Gitea-Event: pull_request` → auto-trigger
  - Handles `X-Gitea-Event: issue_comment` → manual trigger
  - Returns 202 Accepted immediately, processes in background

## Common Pitfalls

1. **Claude CLI wrong flags**: Must use `-p` not `--message`, diff via stdin not in prompt
2. **Missing bot username**: If `BOT_USERNAME` set, manual trigger requires `@mention`
3. **Comment vs PR**: Manual trigger only works on PR comments (validated via `issue.pull_request`)
4. **Webhook events**: Must enable both "Pull Request" AND "Issue Comment" events in Gitea
5. **Background tasks**: All webhook processing is async - errors only visible in logs, not HTTP response
6. **Clone failures**: Service degrades gracefully to simple mode (diff-only) if git clone fails

## Code Style

- Async/await throughout (FastAPI + httpx)
- Type hints required
- Docstrings in Google style
- Chinese comments/logs acceptable (current convention)
- Error handling: Log with `exc_info=True`, return False on failure

## Docker Notes

- Dockerfile includes Node.js + Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- Multi-stage not used (single stage with both Python + Node)
- Health check: `curl http://localhost:8000/health`
- Supports amd64 and arm64 architectures

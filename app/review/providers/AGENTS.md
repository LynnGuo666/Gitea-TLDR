# PROVIDER ENGINE GUIDE

## OVERVIEW
- This directory implements pluggable review engines behind one contract (`ReviewProvider`).

## CORE CONTRACT
- Implement `analyze_pr(...)` as the single provider entrypoint.
- Return `ReviewResult` with normalized fields (`summary_markdown`, `inline_comments`, `usage_metadata`, `model`).
- Register provider in `registry.py` so `ReviewEngine` can resolve it.

## EXPECTED BEHAVIOR
- Providers must accept per-call config overrides (`api_url`, `api_key`, `model`, provider-specific extras).
- Failures should preserve actionable diagnostics but redact secrets.
- Keep output schema stable for downstream persistence/UI rendering.
- Ensure suggestion snippets are markdown code blocks when code is included.
- Forge supports the `review` and `issue` scenarios today; `claude_code` and `codex_cli` only implement `review` — declare support via `supports_issue()` before routing Issue flows.

## SAFETY RULES
- Never leak API keys/tokens in logs, exceptions, or returned text.
- Avoid mutating global CLI config; prefer isolated temp runtime config (like Codex `CODEX_HOME`).
- Keep provider logic provider-specific; shared orchestration belongs in `review_engine.py` or higher service layer.
- `parsing.py` contains shared utilities; prefer importing from there over duplicating in new providers.
- `forge/` tools must validate file paths against repo_path to prevent path traversal.

## FILE RESPONSIBILITIES
| File | Responsibility |
|---|---|
| `base.py` | contract + dataclasses (`ReviewProvider`, `ReviewResult`, `InlineComment`) |
| `registry.py` | provider registration and lookup |
| `parsing.py` | shared parsing utilities (`extract_json_payload`, `parse_inline_comment`, `coerce_int`, `extract_actionable_error`) |
| `claude_code.py` | Claude CLI invocation + result normalization |
| `codex_cli.py` | Codex CLI invocation + isolated config/runtime |
| `forge/` | Agentic engine — direct Anthropic API with tool use |
| `forge/provider.py` | `ForgeProvider` — ReviewProvider adapter for the forge engine |
| `forge/engine.py` | `ForgeEngine` — agentic loop core (turn loop + tool execution) |
| `forge/api_client.py` | `AnthropicClient` — direct Messages API calls |
| `forge/types.py` | core data types (`ForgeResult`, `ForgeUsage`, `ToolDefinition`) |
| `forge/system_prompts.py` | system prompt builders per scenario (includes `ISSUE_FOCUS_MAP`) |
| `forge/tools/` | tool definitions + executors (`read_file`, `search_code`, `list_directory`, `glob_files`, `lsp`, `submit_review`, `submit_analysis`) |
| `forge/scenarios/` | scenario runners (`review.py`, `issue.py` — `run_issue` + `finalize_issue_payload` 三层降级) |
| `usage_proxy.py` | SSE proxy for capturing Claude CLI usage (only used by claude_code) |

## ANTI-PATTERNS
- Do not add business policy decisions (webhook/event flow) in providers.
- Do not change response shape ad-hoc per provider.
- Do not use hardcoded model/provider names outside config defaults.

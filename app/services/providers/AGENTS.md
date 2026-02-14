# PROVIDER ENGINE GUIDE

## OVERVIEW
- This directory implements pluggable review engines behind one contract (`ReviewProvider`).

## CORE CONTRACT
- Implement both methods:
  - `analyze_pr(...)` for full-repo/context mode.
  - `analyze_pr_simple(...)` for diff-only fallback mode.
- Return `ReviewResult` with normalized fields (`summary_markdown`, `inline_comments`, `usage_metadata`, `model`).
- Register provider in `registry.py` so `ReviewEngine` can resolve it.

## EXPECTED BEHAVIOR
- Providers must accept per-call config overrides (`api_url`, `api_key`, `model`, provider-specific extras).
- Failures should preserve actionable diagnostics but redact secrets.
- Keep output schema stable for downstream persistence/UI rendering.
- Ensure suggestion snippets are markdown code blocks when code is included.

## SAFETY RULES
- Never leak API keys/tokens in logs, exceptions, or returned text.
- Avoid mutating global CLI config; prefer isolated temp runtime config (like Codex `CODEX_HOME`).
- Keep provider logic provider-specific; shared orchestration belongs in `review_engine.py` or higher service layer.

## FILE RESPONSIBILITIES
| File | Responsibility |
|---|---|
| `base.py` | contract + dataclasses (`ReviewProvider`, `ReviewResult`, `InlineComment`) |
| `registry.py` | provider registration and lookup |
| `claude_code.py` | Claude CLI invocation + result normalization |
| `codex_cli.py` | Codex CLI invocation + isolated config/runtime |

## ANTI-PATTERNS
- Do not add business policy decisions (webhook/event flow) in providers.
- Do not change response shape ad-hoc per provider.
- Do not use hardcoded model/provider names outside config defaults.

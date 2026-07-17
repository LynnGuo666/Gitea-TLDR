"""PR 审查编排子包（阶段 8 拆分自 webhook_handler._perform_review）。

把原 603 行的 `_perform_review` 按职责拆成协作类：

- `ConfigResolver`：获取 repo / config / credential + 解析 engine / api_url /
  api_key / wire_api / model / focus / features + 缺失分支 raise。
- `RunRecorder`：DB 写入协调（analysis_run / provider_run / annotations /
  usage_event 的创建与收尾）。
- `ReviewPublisher`：评论发布（变更概览 + 审查发现）、create_review /
  request_reviewer、create_commit_status。
- `ReviewOrchestrator`：编排上述三者 + 幂等检查 + 克隆 + analyze_pr + 异常处理。

`WebhookHandler._perform_review` 变为薄委托 `orchestrator.run(...)`。
"""

from .orchestrator import ReviewOrchestrator
from .config_resolver import ConfigResolver, ReviewConfig
from .publisher import ReviewPublisher
from .recorder import RunRecorder

__all__ = [
    "ReviewOrchestrator",
    "ConfigResolver",
    "ReviewConfig",
    "RunRecorder",
    "ReviewPublisher",
]

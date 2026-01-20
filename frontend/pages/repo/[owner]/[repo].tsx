import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState, useCallback } from 'react';
import { RepoIcon, BotIcon, SettingsIcon, RefreshIcon } from '../../../components/icons';
import { useToast, Skeleton } from '../../../components/ui';
import { PublicConfig, RepoClaudeConfig } from '../../../lib/types';
import { AuthContext } from '../../../lib/auth';

const defaultEvents = ['pull_request', 'issue_comment'];
const reviewCatalog = [
  {
    key: 'quality',
    label: '质量保障',
    detail: '架构、风格一致性、重复代码',
  },
  {
    key: 'security',
    label: '安全合规',
    detail: '权限、依赖、输入校验与密钥',
  },
  {
    key: 'performance',
    label: '性能体验',
    detail: '慢查询、循环、资源热点',
  },
  {
    key: 'logic',
    label: '业务逻辑',
    detail: '边界条件、回归风险、异常链路',
  },
];

type WebhookStatus = {
  configured: boolean;
  active: boolean;
  webhook_id: number | null;
  events: string[];
  url: string | null;
  can_setup_webhook?: boolean;
};

export default function RepoConfigPage() {
  const router = useRouter();
  const { owner, repo } = router.query;
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [webhookStatus, setWebhookStatus] = useState<WebhookStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [events, setEvents] = useState<string[]>(defaultEvents);
  const [bringBot, setBringBot] = useState(true);
  const [reviewFocus, setReviewFocus] = useState<string[]>([
    'quality',
    'security',
    'performance',
  ]);
  // Claude 配置状态
  const [claudeConfig, setClaudeConfig] = useState<RepoClaudeConfig | null>(null);
  const [claudeBaseUrl, setClaudeBaseUrl] = useState('');
  const [claudeAuthToken, setClaudeAuthToken] = useState('');
  const [claudeConfigLoading, setClaudeConfigLoading] = useState(true);
  const [claudeSaving, setClaudeSaving] = useState(false);

  const { status: authStatus, beginLogin } = useContext(AuthContext);
  const { addToast } = useToast();
  const requiresLogin = authStatus.enabled && !authStatus.loggedIn;

  const fetchWebhookStatus = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setStatusLoading(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/webhook-status`);
      if (res.ok) {
        const data = await res.json();
        setWebhookStatus(data);
        // 如果已配置，同步 events
        if (data.configured && data.events?.length) {
          setEvents(data.events);
        }
      } else {
        setWebhookStatus(null);
      }
    } catch {
      setWebhookStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  const fetchClaudeConfig = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setClaudeConfigLoading(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/claude-config`);
      if (res.ok) {
        const data = await res.json();
        setClaudeConfig(data);
        if (data.anthropic_base_url) {
          setClaudeBaseUrl(data.anthropic_base_url);
        }
      } else {
        setClaudeConfig(null);
      }
    } catch {
      setClaudeConfig(null);
    } finally {
      setClaudeConfigLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  useEffect(() => {
    fetch('/api/config/public')
      .then((res) => res.json())
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  const canEditRepo = webhookStatus?.can_setup_webhook ?? true;

  useEffect(() => {
    if (owner && repo && !requiresLogin) {
      fetchWebhookStatus();
      fetchClaudeConfig();
    } else {
      setStatusLoading(false);
      setClaudeConfigLoading(false);
    }
  }, [owner, repo, requiresLogin, fetchWebhookStatus, fetchClaudeConfig]);

  const toggleEvent = (event: string) => {
    setEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  const toggleFocus = (key: string) => {
    setReviewFocus((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    );
  };

  const enableWebhook = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setToggling(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events, bring_bot: bringBot }),
      });
      const data = await res.json();
      if (res.ok) {
        addToast('Webhook 已启用', 'success');
        await fetchWebhookStatus();
      } else {
        addToast(data.detail || 'Webhook 配置失败', 'error');
      }
    } catch {
      addToast('无法连接后端', 'error');
    } finally {
      setToggling(false);
    }
  };

  const disableWebhook = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setToggling(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/webhook`, {
        method: 'DELETE',
      });
      if (res.ok) {
        addToast('Webhook 已禁用', 'success');
        setWebhookStatus({
          configured: false,
          active: false,
          webhook_id: null,
          events: [],
          url: null,
        });
      } else {
        const data = await res.json();
        addToast(data.detail || '删除 Webhook 失败', 'error');
      }
    } catch {
      addToast('无法连接后端', 'error');
    } finally {
      setToggling(false);
    }
  };

  const handleToggle = () => {
    if (webhookStatus?.configured) {
      disableWebhook();
    } else {
      enableWebhook();
    }
  };

  const saveClaudeConfig = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setClaudeSaving(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/claude-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          anthropic_base_url: claudeBaseUrl || null,
          anthropic_auth_token: claudeAuthToken || null,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        addToast('Claude 配置已保存', 'success');
        setClaudeConfig({
          configured: true,
          anthropic_base_url: data.anthropic_base_url,
          has_auth_token: data.has_auth_token,
        });
        // 清空 token 输入框（安全考虑）
        setClaudeAuthToken('');
      } else {
        addToast(data.detail || '保存失败', 'error');
      }
    } catch {
      addToast('无法连接后端', 'error');
    } finally {
      setClaudeSaving(false);
    }
  };

  if (!owner || !repo) {
    return null;
  }

  const isWebhookEnabled = webhookStatus?.configured && webhookStatus?.active;

  return (
    <>
      <Head>
        <title>{`${owner}/${repo} - 配置`}</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="repo-header">
            <button className="back-button" onClick={() => router.push('/')}>
              ← 返回
            </button>
            <div className="repo-title">
              <span className="icon-badge">
                <RepoIcon size={20} />
              </span>
              <h1>{`${owner}/${repo}`}</h1>
            </div>
          </div>
        </section>

        {/* Webhook 状态卡片 */}
        <section className="card">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <SettingsIcon size={18} />
              </span>
              <h2>自动审查</h2>
            </div>
            {!requiresLogin && !statusLoading && (
              <button
                className={`refresh-button ${statusLoading ? 'spinning' : ''}`}
                onClick={fetchWebhookStatus}
                title="刷新状态"
              >
                <RefreshIcon size={16} />
              </button>
            )}
          </div>

          {requiresLogin ? (
            <div className="webhook-status-card">
              <div className="webhook-status-info">
                <h3>需要登录</h3>
                <p>连接 Gitea 后才能查看和配置 Webhook</p>
              </div>
              <button className="primary-button" onClick={beginLogin}>
                登录
              </button>
            </div>
          ) : statusLoading ? (
            <div className="webhook-status-card">
              <Skeleton width={200} height={20} />
              <Skeleton width={52} height={28} />
            </div>
          ) : (
            <div className="webhook-status-card">
              <div className="webhook-status-info">
                <h3>
                  <span className={`status-dot ${isWebhookEnabled ? 'active' : 'inactive'}`} />
                  {isWebhookEnabled ? 'Webhook 已启用' : 'Webhook 未启用'}
                </h3>
                <p>
                  {canEditRepo
                    ? isWebhookEnabled
                      ? `监听事件: ${webhookStatus?.events?.join(', ') || '无'}`
                      : '启用后，PR 将自动触发代码审查'
                    : '组织仓库需要组织管理员权限才能修改配置'}
                </p>
              </div>
              <div
                className={`toggle-switch-track ${isWebhookEnabled ? 'active' : ''} ${toggling ? 'loading' : ''} ${canEditRepo ? '' : 'disabled'}`}
                onClick={toggling || !canEditRepo ? undefined : handleToggle}
                role="switch"
                aria-checked={isWebhookEnabled}
                aria-disabled={!canEditRepo}
                tabIndex={canEditRepo ? 0 : -1}
                onKeyDown={(e) => {
                  if (!canEditRepo) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    if (!toggling) handleToggle();
                  }
                }}
              >
                <div className="toggle-switch-thumb" />
              </div>
            </div>
          )}

          {/* 高级配置 - 仅在未启用时显示 */}
          {!requiresLogin && !statusLoading && !isWebhookEnabled && canEditRepo && (
            <>
              <p className="muted" style={{ marginTop: 'var(--spacing-md)' }}>
                启用前可选择监听的事件：
              </p>
              <div className="chip-row" style={{ marginTop: 'var(--spacing-sm)' }}>
                {defaultEvents.map((event) => (
                  <button
                    key={event}
                    className={`chip ${events.includes(event) ? 'active' : ''}`}
                    onClick={() => toggleEvent(event)}
                  >
                    {event}
                  </button>
                ))}
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={bringBot}
                    onChange={(e) => setBringBot(e.target.checked)}
                  />
                  <span>邀请 bot 协作</span>
                </label>
              </div>
            </>
          )}
        </section>

        {/* 审查方向 */}
        <section className="card">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <BotIcon size={18} />
              </span>
              <h2>审查方向</h2>
            </div>
            <span className="badge-soft">{reviewFocus.length} 个已启用</span>
          </div>
          <div className="focus-grid">
            {reviewCatalog.map((item) => (
              <button
                key={item.key}
                className={`focus-chip ${reviewFocus.includes(item.key) ? 'active' : ''}`}
                onClick={() => toggleFocus(item.key)}
              >
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.detail}</p>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Claude 配置 */}
        <section className="card">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <SettingsIcon size={18} />
              </span>
              <h2>Claude 配置</h2>
            </div>
            {claudeConfig?.has_auth_token && (
              <span className="badge-soft success">已配置 Token</span>
            )}
          </div>

          {requiresLogin ? (
            <p className="muted">登录后可配置 Claude API</p>
          ) : claudeConfigLoading ? (
            <div style={{ padding: 'var(--spacing-md)' }}>
              <Skeleton width="100%" height={40} />
              <div style={{ marginTop: 'var(--spacing-sm)' }}>
                <Skeleton width="100%" height={40} />
              </div>
            </div>
          ) : (
            <>
              <div className="input-grid">
                <label className="input-field">
                  <span>Base URL</span>
                  <input
                    type="text"
                    value={claudeBaseUrl}
                    onChange={(e) => setClaudeBaseUrl(e.target.value)}
                    placeholder="https://api.anthropic.com (留空使用默认)"
                    disabled={!canEditRepo}
                  />
                </label>
                <label className="input-field">
                  <span>API Key</span>
                  <input
                    type="password"
                    value={claudeAuthToken}
                    onChange={(e) => setClaudeAuthToken(e.target.value)}
                    placeholder={claudeConfig?.has_auth_token ? '已配置（输入新值覆盖）' : 'sk-ant-...'}
                    disabled={!canEditRepo}
                  />
                </label>
              </div>
              <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
                <button
                  className="primary-button"
                  onClick={saveClaudeConfig}
                  disabled={claudeSaving || !canEditRepo}
                >
                  {claudeSaving ? '保存中...' : '保存配置'}
                </button>
                <span className="muted small">
                  {canEditRepo
                    ? '配置后，审查 PR 时将使用此仓库的 API Key'
                    : '组织仓库需要组织管理员权限才能修改 Claude 配置'}
                </span>
              </div>
            </>
          )}
        </section>

        {/* 服务信息 */}
        {config && (
          <section className="card">
            <div className="panel-header">
              <h3>服务信息</h3>
            </div>
            <dl className="status-list">
              <div>
                <dt>Gitea 实例</dt>
                <dd>{config.gitea_url}</dd>
              </div>
              <div>
                <dt>Bot 账号</dt>
                <dd>{config.bot_username || '未配置'}</dd>
              </div>
              {webhookStatus?.url && (
                <div>
                  <dt>Webhook URL</dt>
                  <dd style={{ fontSize: '0.85rem', wordBreak: 'break-all' }}>
                    {webhookStatus.url}
                  </dd>
                </div>
              )}
            </dl>
          </section>
        )}
      </main>
    </>
  );
}

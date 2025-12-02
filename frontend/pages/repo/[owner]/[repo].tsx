import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState } from 'react';
import { RepoIcon, BotIcon, SettingsIcon } from '../../../components/icons';
import { PublicConfig } from '../../../lib/types';
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

export default function RepoConfigPage() {
  const router = useRouter();
  const { owner, repo } = router.query;
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [events, setEvents] = useState<string[]>(defaultEvents);
  const [bringBot, setBringBot] = useState(true);
  const [reviewFocus, setReviewFocus] = useState<string[]>([
    'quality',
    'security',
    'performance',
  ]);
  const { status: authStatus, beginLogin } = useContext(AuthContext);
  const requiresLogin = authStatus.enabled && !authStatus.loggedIn;

  useEffect(() => {
    fetch('/api/config/public')
      .then((res) => res.json())
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

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

  const setupRepo = async () => {
    if (requiresLogin || !owner || !repo) return;

    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/setup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ events, bring_bot: bringBot }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage(
          `Webhook 已就绪 (ID: ${data.webhook_id})，回调: ${data.webhook_url}`
        );
      } else {
        setMessage(data.detail || 'Webhook 配置失败');
      }
    } catch (error) {
      setMessage('无法连接后端，请检查服务是否启动');
    } finally {
      setLoading(false);
    }
  };

  if (!owner || !repo) {
    return null;
  }

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
                className={`focus-chip ${
                  reviewFocus.includes(item.key) ? 'active' : ''
                }`}
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

        <section className="card">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <SettingsIcon size={18} />
              </span>
              <h2>Webhook 配置</h2>
            </div>
          </div>
          <div className="automation-grid">
            <div className="chip-row">
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
          </div>
          <div className="automation-footer">
            <button
              className="primary-button"
              onClick={requiresLogin ? beginLogin : setupRepo}
              disabled={loading || requiresLogin}
            >
              {requiresLogin ? '登录以继续' : loading ? '配置中…' : '自动配置 Webhook'}
            </button>
            {message && <p className="muted">{message}</p>}
            {requiresLogin && (
              <p className="muted">连接 Gitea 后才能为仓库配置 Webhook。</p>
            )}
          </div>
        </section>

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
            </dl>
          </section>
        )}
      </main>
    </>
  );
}

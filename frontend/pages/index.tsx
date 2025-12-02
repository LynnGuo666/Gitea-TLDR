import Head from 'next/head';
import { useEffect, useMemo, useState } from 'react';

type Repo = {
  id: number;
  name: string;
  owner: { username?: string; login?: string; full_name?: string };
  full_name?: string;
  private?: boolean;
};

type PublicConfig = {
  gitea_url: string;
  bot_username?: string | null;
  debug: boolean;
};

const defaultEvents = ['pull_request', 'issue_comment'];

export default function Home() {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState('');
  const [message, setMessage] = useState('');
  const [events, setEvents] = useState<string[]>(defaultEvents);
  const [bringBot, setBringBot] = useState(true);

  useEffect(() => {
    fetch('/api/config/public')
      .then((res) => res.json())
      .then(setConfig)
      .catch(() => setConfig(null));

    fetch('/api/repos')
      .then((res) => res.json())
      .then((data) => setRepos(data.repos || []))
      .catch(() => setRepos([]));
  }, []);

  const repoOptions = useMemo(() => {
    return repos.map((r) => ({
      key: r.full_name || `${r.owner?.username || r.owner?.login}/${r.name}`,
      label: `${r.owner?.username || r.owner?.login}/${r.name}${r.private ? ' (private)' : ''}`,
      owner: r.owner?.username || r.owner?.login || '',
      name: r.name,
    }));
  }, [repos]);

  const toggleEvent = (event: string) => {
    setEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  const setupRepo = async () => {
    if (!selectedRepo) {
      setMessage('请选择需要自动审查的仓库');
      return;
    }
    const option = repoOptions.find((r) => r.key === selectedRepo);
    if (!option) return;

    setLoading(true);
    setMessage('');
    try {
      const res = await fetch(`/api/repos/${option.owner}/${option.name}/setup`, {
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

  return (
    <>
      <Head>
        <title>Gitea PR Reviewer 控制台</title>
      </Head>
      <main className="container">
        <div className="card">
          <div className="section-header">
            <h1>Gitea PR Reviewer</h1>
            <span className="badge">Next.js 静态前端</span>
          </div>
          <p className="small">
            使用 Gitea OAuth 登录后选择可管理的仓库，自动为每个仓库配置 Webhook，并邀请 bot 参与。
          </p>
          <div className="grid">
            <div className="stat">
              <p className="stat-title">Gitea 实例</p>
              <p className="stat-value">{config?.gitea_url || '读取中...'}</p>
              <p className="small">使用服务器侧 token 进行 API 调用</p>
            </div>
            <div className="stat">
              <p className="stat-title">Bot 账号</p>
              <p className="stat-value">{config?.bot_username || '未配置'}</p>
              <p className="small">用于协作与审查邀请</p>
            </div>
            <div className="stat">
              <p className="stat-title">事件监听</p>
              <p className="stat-value">pull_request / issue_comment</p>
              <p className="small">静态导出 + FastAPI 同进程托管</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="section-header">
            <h2>1. OAuth 登录</h2>
            <span className="badge">Gitea OAuth App</span>
          </div>
          <p className="small">
            请在 Gitea 创建 OAuth2 应用并将回调指向前端入口。前端静态导出后会随 FastAPI 一并启动，可直接通过
            <code> /ui </code>
            访问。
          </p>
          <div className="flex-column">
            <div className="tag">回调: &lt;base-url&gt;/ui/oauth/callback</div>
            <div className="tag">授权作用域: repo、admin:repo_hook、write:user</div>
          </div>
        </div>

        <div className="card">
          <div className="section-header">
            <h2>2. 选择仓库并一键配置</h2>
            <span className="badge">Webhook + Bot</span>
          </div>
          <div className="input-row">
            <label>可管理仓库</label>
            <select
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
            >
              <option value="">请选择仓库</option>
              {repoOptions.map((repo) => (
                <option key={repo.key} value={repo.key}>
                  {repo.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex">
            <div className="tag" onClick={() => toggleEvent('pull_request')}>
              <input
                type="checkbox"
                checked={events.includes('pull_request')}
                readOnly
              />
              pull_request
            </div>
            <div className="tag" onClick={() => toggleEvent('issue_comment')}>
              <input
                type="checkbox"
                checked={events.includes('issue_comment')}
                readOnly
              />
              issue_comment
            </div>
          </div>

          <div className="input-row">
            <label>邀请 bot 协作</label>
            <input
              type="checkbox"
              checked={bringBot}
              onChange={(e) => setBringBot(e.target.checked)}
            />
          </div>

          <div className="flex" style={{ alignItems: 'center' }}>
            <button className="button" onClick={setupRepo} disabled={loading}>
              {loading ? '配置中...' : '自动配置 Webhook'}
            </button>
            {message && <span className="small">{message}</span>}
          </div>
        </div>

        <div className="card">
          <div className="section-header">
            <h2>3. 审查重点与用量</h2>
            <span className="badge">运营侧</span>
          </div>
          <p className="small">
            管理员可以在 FastAPI 侧查看 Claude Code token 用量并设定每个仓库的审查重点。前端页面将继续补充额度与方向配置面板。
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>方向</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <div className="tag">质量</div>
                </td>
                <td className="small">代码风格、可维护性、重复代码等问题</td>
              </tr>
              <tr>
                <td>
                  <div className="tag">安全</div>
                </td>
                <td className="small">依赖漏洞、危险 API、鉴权逻辑风险</td>
              </tr>
              <tr>
                <td>
                  <div className="tag">性能</div>
                </td>
                <td className="small">慢查询、循环、内存/IO 热点</td>
              </tr>
              <tr>
                <td>
                  <div className="tag">逻辑</div>
                </td>
                <td className="small">流程漏洞、边界条件、空指针等逻辑问题</td>
              </tr>
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}

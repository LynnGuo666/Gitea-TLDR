import Head from 'next/head';
import { useEffect, useState } from 'react';
import { UserIcon } from '../components/icons';
import { PublicConfig } from '../lib/types';

export default function SettingsPage() {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [remainingCredits, setRemainingCredits] = useState(320000);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/config/public')
      .then((res) => res.json())
      .then((data) => {
        setConfig(data);
        if (data?.gitea_url) {
          setBaseUrl((prev) => prev || data.gitea_url);
        }
      })
      .catch(() => setConfig(null));
  }, []);

  const refreshUsage = () => {
    setRemainingCredits((prev) => Math.max(0, prev - 1200));
    setMessage('已同步最新余额 (示例数据)');
  };

  const handleSave = () => {
    setMessage('配置已保存 (仅演示效果)');
  };

  return (
    <>
      <Head>
        <title>用户中心 - Gitea PR Reviewer</title>
      </Head>
      <main className="dashboard">
        <section className="card account-panel">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <UserIcon size={18} />
              </span>
              <h2>用户中心</h2>
            </div>
            <button className="ghost-button" onClick={refreshUsage}>
              刷新用量
            </button>
          </div>
          <p className="muted">
            Gitea {config?.gitea_url || '读取中...'} · Bot{' '}
            {config?.bot_username || '未配置'}
          </p>
          <div className="input-grid">
            <label className="input-field">
              <span>Claude BASEURL</span>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.anthropic.com"
              />
            </label>
            <label className="input-field">
              <span>API Key</span>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-••••••••"
              />
            </label>
          </div>
          <div className="account-footer">
            <div className="usage-pill">
              <span>剩余用量</span>
              <strong>{remainingCredits.toLocaleString()} tokens</strong>
            </div>
            <button className="primary-button" onClick={handleSave}>
              保存配置
            </button>
          </div>
          {message && <p className="muted">{message}</p>}
        </section>
      </main>
    </>
  );
}

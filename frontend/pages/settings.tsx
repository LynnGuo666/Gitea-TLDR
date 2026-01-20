import Head from 'next/head';
import Image from 'next/image';
import { useContext, useEffect, useState } from 'react';
import { UserIcon } from '../components/icons';
import { AuthContext } from '../lib/auth';
import { PublicConfig, UsageSummary } from '../lib/types';

export default function SettingsPage() {
  const { status: authStatus } = useContext(AuthContext);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [stats, setStats] = useState<UsageSummary | null>(null);
  const [reviewCount, setReviewCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // 获取公共配置
        const configRes = await fetch('/api/config/public');
        if (configRes.ok) {
          const configData = await configRes.json();
          setConfig(configData);
        }

        // 获取使用统计
        const statsRes = await fetch('/api/stats');
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData.summary);
          // 统计审查次数
          setReviewCount(statsData.details?.length || 0);
        }
      } catch (error) {
        console.error('Failed to fetch settings data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const refreshStats = async () => {
    try {
      const statsRes = await fetch('/api/stats');
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData.summary);
        setReviewCount(statsData.details?.length || 0);
      }
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
  };

  return (
    <>
      <Head>
        <title>用户中心 - Gitea PR Reviewer</title>
      </Head>
      <main className="dashboard">
        {/* 用户信息卡片 */}
        <section className="card account-panel">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <UserIcon size={18} />
              </span>
              <h2>用户信息</h2>
            </div>
          </div>

          {authStatus.loggedIn && authStatus.user ? (
            <div className="user-info-card">
              <div className="user-avatar">
                {authStatus.user.avatar_url ? (
                  <Image
                    src={authStatus.user.avatar_url}
                    alt={authStatus.user.username || 'avatar'}
                    width={64}
                    height={64}
                  />
                ) : (
                  <span className="avatar-placeholder large">
                    {(authStatus.user.username || 'U')[0].toUpperCase()}
                  </span>
                )}
              </div>
              <div className="user-details">
                <h3>{authStatus.user.full_name || authStatus.user.username}</h3>
                <p className="muted">@{authStatus.user.username}</p>
                <p className="muted small">
                  Gitea: {config?.gitea_url || '...'}
                </p>
              </div>
            </div>
          ) : (
            <p className="muted">未登录</p>
          )}
        </section>

        {/* 使用统计卡片 */}
        <section className="card account-panel">
          <div className="panel-header">
            <div className="section-title">
              <h2>使用统计</h2>
            </div>
            <button className="ghost-button" onClick={refreshStats}>
              刷新
            </button>
          </div>

          {loading ? (
            <div className="stats-loading">
              <p className="muted">加载中...</p>
            </div>
          ) : (
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-value">{reviewCount}</span>
                <span className="stat-label">PR 审查次数</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{stats?.total_claude_calls || 0}</span>
                <span className="stat-label">Claude API 调用</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">
                  {formatNumber((stats?.total_input_tokens || 0) + (stats?.total_output_tokens || 0))}
                </span>
                <span className="stat-label">总 Token 使用量</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{stats?.total_gitea_calls || 0}</span>
                <span className="stat-label">Gitea API 调用</span>
              </div>
            </div>
          )}
        </section>

        {/* 服务状态卡片 */}
        <section className="card account-panel">
          <div className="panel-header">
            <div className="section-title">
              <h2>服务状态</h2>
            </div>
          </div>

          <div className="service-status-list">
            <div className="status-item">
              <span className="status-label">Bot 用户名</span>
              <span className="status-value">
                {config?.bot_username || <span className="muted">未配置</span>}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">Debug 模式</span>
              <span className={`status-badge ${config?.debug ? 'active' : ''}`}>
                {config?.debug ? '开启' : '关闭'}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">OAuth 登录</span>
              <span className={`status-badge ${config?.oauth_enabled ? 'active' : ''}`}>
                {config?.oauth_enabled ? '已启用' : '未启用'}
              </span>
            </div>
          </div>

          <p className="muted small" style={{ marginTop: '1rem' }}>
            Claude 配置（Base URL / API Key）请在各仓库的配置页面中单独设置
          </p>
        </section>
      </main>
    </>
  );
}

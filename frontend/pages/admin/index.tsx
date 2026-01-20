import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState } from 'react';
import { ChartIcon, RepoIcon, UsageIcon, RefreshIcon } from '../../components/icons';
import { AuthContext } from '../../lib/auth';

type DashboardStats = {
  reviews: {
    total: number;
    today: number;
    week: number;
    month: number;
  };
  tokens: {
    total: number;
    today: number;
    week: number;
    month: number;
  };
  webhooks: {
    total: number;
    today: number;
    success_rate: number;
  };
  repositories: {
    total: number;
    active: number;
  };
};

export default function AdminDashboard() {
  const router = useRouter();
  const { status: authStatus } = useContext(AuthContext);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/dashboard/stats');
      if (res.status === 403) {
        router.push('/');
        return;
      }
      if (!res.ok) {
        throw new Error('获取统计数据失败');
      }
      const data = await res.json();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authStatus.loggedIn) {
      fetchStats();
    }
  }, [authStatus.loggedIn]);

  if (!authStatus.loggedIn) {
    return (
      <main className="dashboard">
        <section className="card">
          <h1>管理后台</h1>
          <p>需要登录后才能访问管理后台</p>
        </section>
      </main>
    );
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  return (
    <>
      <Head>
        <title>管理后台 - Dashboard</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="panel-header">
            <h1>管理后台</h1>
            <button
              className={`refresh-button ${loading ? 'spinning' : ''}`}
              onClick={fetchStats}
              disabled={loading}
            >
              <RefreshIcon size={16} />
            </button>
          </div>

          {error && (
            <div className="error-message" style={{ marginTop: '1rem' }}>
              {error}
            </div>
          )}

          {loading && !stats ? (
            <div style={{ padding: '2rem', textAlign: 'center' }}>
              <p className="muted">加载中...</p>
            </div>
          ) : stats ? (
            <>
              {/* 统计卡片网格 */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                  gap: 'var(--spacing-md)',
                  marginTop: 'var(--spacing-lg)',
                }}
              >
                {/* 审查统计 */}
                <div className="stat-card">
                  <div className="stat-header">
                    <ChartIcon size={20} />
                    <h3>审查次数</h3>
                  </div>
                  <div className="stat-value">{formatNumber(stats.reviews.total)}</div>
                  <div className="stat-details">
                    <span>今日: {stats.reviews.today}</span>
                    <span>本周: {stats.reviews.week}</span>
                    <span>本月: {stats.reviews.month}</span>
                  </div>
                </div>

                {/* Token 统计 */}
                <div className="stat-card">
                  <div className="stat-header">
                    <UsageIcon size={20} />
                    <h3>Token 消耗</h3>
                  </div>
                  <div className="stat-value">{formatNumber(stats.tokens.total)}</div>
                  <div className="stat-details">
                    <span>今日: {formatNumber(stats.tokens.today)}</span>
                    <span>本周: {formatNumber(stats.tokens.week)}</span>
                    <span>本月: {formatNumber(stats.tokens.month)}</span>
                  </div>
                </div>

                {/* Webhook 统计 */}
                <div className="stat-card">
                  <div className="stat-header">
                    <ChartIcon size={20} />
                    <h3>Webhook</h3>
                  </div>
                  <div className="stat-value">{stats.webhooks.total}</div>
                  <div className="stat-details">
                    <span>今日: {stats.webhooks.today}</span>
                    <span>成功率: {stats.webhooks.success_rate.toFixed(1)}%</span>
                  </div>
                </div>

                {/* 仓库统计 */}
                <div className="stat-card">
                  <div className="stat-header">
                    <RepoIcon size={20} />
                    <h3>仓库</h3>
                  </div>
                  <div className="stat-value">{stats.repositories.total}</div>
                  <div className="stat-details">
                    <span>活跃: {stats.repositories.active}</span>
                  </div>
                </div>
              </div>

              {/* 快捷导航 */}
              <div style={{ marginTop: 'var(--spacing-xl)' }}>
                <h2 style={{ marginBottom: 'var(--spacing-md)' }}>快捷操作</h2>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: 'var(--spacing-md)',
                  }}
                >
                  <button
                    className="card-button"
                    onClick={() => router.push('/admin/config')}
                  >
                    <h3>全局配置</h3>
                    <p className="muted">管理系统配置</p>
                  </button>
                  <button
                    className="card-button"
                    onClick={() => router.push('/admin/repos')}
                  >
                    <h3>仓库管理</h3>
                    <p className="muted">批量操作仓库</p>
                  </button>
                  <button
                    className="card-button"
                    onClick={() => router.push('/admin/reviews')}
                  >
                    <h3>审查历史</h3>
                    <p className="muted">查看所有审查记录</p>
                  </button>
                  <button
                    className="card-button"
                    onClick={() => router.push('/admin/webhooks')}
                  >
                    <h3>Webhook 日志</h3>
                    <p className="muted">查看请求日志</p>
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </section>
      </main>
    </>
  );
}

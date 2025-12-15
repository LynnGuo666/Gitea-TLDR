import Head from 'next/head';
import { useEffect, useState, useMemo } from 'react';
import { UsageIcon, RefreshIcon } from '../components/icons';
import { CardSkeleton } from '../components/ui';

const USD_PER_MILLION_INPUT = 3;  // Claude input tokens
const USD_PER_MILLION_OUTPUT = 15; // Claude output tokens

type UsageStat = {
  id: number;
  repository_id: number;
  review_session_id: number | null;
  date: string | null;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  gitea_api_calls: number;
  claude_api_calls: number;
  clone_operations: number;
};

type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_gitea_calls: number;
  total_claude_calls: number;
  total_clone_operations: number;
  review_count: number;
};

type StatsResponse = {
  summary: UsageSummary;
  details: UsageStat[];
};

export default function UsagePage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);

  const fetchStats = async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/stats');
      if (!res.ok) {
        if (res.status === 503) {
          setError('数据库未启用，无法获取统计数据');
        } else {
          setError('获取统计数据失败');
        }
        setStats(null);
      } else {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      setError('网络错误，无法连接服务器');
      setStats(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const totalTokens = useMemo(() => {
    if (!stats?.summary) return 0;
    return stats.summary.total_input_tokens + stats.summary.total_output_tokens;
  }, [stats]);

  const totalRequests = useMemo(() => {
    return stats?.summary?.total_claude_calls || 0;
  }, [stats]);

  const usdCost = useMemo(() => {
    if (!stats?.summary) return '0.00';
    const inputCost = (stats.summary.total_input_tokens / 1_000_000) * USD_PER_MILLION_INPUT;
    const outputCost = (stats.summary.total_output_tokens / 1_000_000) * USD_PER_MILLION_OUTPUT;
    return (inputCost + outputCost).toFixed(2);
  }, [stats]);

  // Group details by date
  const groupedByDate = useMemo(() => {
    if (!stats?.details?.length) return [];
    const groups: { [key: string]: { date: string; inputTokens: number; outputTokens: number; requests: number } } = {};

    for (const stat of stats.details) {
      const dateKey = stat.date || 'unknown';
      if (!groups[dateKey]) {
        groups[dateKey] = { date: dateKey, inputTokens: 0, outputTokens: 0, requests: 0 };
      }
      groups[dateKey].inputTokens += stat.estimated_input_tokens;
      groups[dateKey].outputTokens += stat.estimated_output_tokens;
      groups[dateKey].requests += stat.claude_api_calls;
    }

    return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date));
  }, [stats]);

  if (loading) {
    return (
      <>
        <Head>
          <title>用量 - Gitea PR Reviewer</title>
        </Head>
        <main className="dashboard">
          <CardSkeleton />
        </main>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>用量 - Gitea PR Reviewer</title>
      </Head>
      <main className="dashboard">
        <section className="card admin-panel">
          <div className="panel-header">
            <div className="section-title">
              <span className="icon-badge">
                <UsageIcon size={18} />
              </span>
              <h2>用量统计</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button
                className={`refresh-button ${refreshing ? 'spinning' : ''}`}
                onClick={() => fetchStats(true)}
                disabled={refreshing}
                title="刷新统计"
              >
                <RefreshIcon size={18} />
              </button>
              <div className="cost-pill">
                <span>预计美元</span>
                <strong>${usdCost}</strong>
              </div>
            </div>
          </div>

          {error ? (
            <div className="empty-state">
              <p>{error}</p>
              <button className="primary-button" onClick={() => fetchStats()}>
                重试
              </button>
            </div>
          ) : (
            <>
              <div className="usage-summary">
                <div>
                  <p>总 tokens</p>
                  <strong>{totalTokens.toLocaleString()}</strong>
                </div>
                <div>
                  <p>输入 tokens</p>
                  <strong>{(stats?.summary?.total_input_tokens || 0).toLocaleString()}</strong>
                </div>
                <div>
                  <p>输出 tokens</p>
                  <strong>{(stats?.summary?.total_output_tokens || 0).toLocaleString()}</strong>
                </div>
                <div>
                  <p>API 调用</p>
                  <strong>{totalRequests.toLocaleString()}</strong>
                </div>
                <div>
                  <p>审查次数</p>
                  <strong>{(stats?.summary?.review_count || 0).toLocaleString()}</strong>
                </div>
              </div>

              {groupedByDate.length > 0 ? (
                <table className="usage-table">
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>输入 Tokens</th>
                      <th>输出 Tokens</th>
                      <th>请求</th>
                      <th>费用</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupedByDate.map((entry) => {
                      const cost = (
                        (entry.inputTokens / 1_000_000) * USD_PER_MILLION_INPUT +
                        (entry.outputTokens / 1_000_000) * USD_PER_MILLION_OUTPUT
                      ).toFixed(2);
                      return (
                        <tr key={entry.date}>
                          <td>{entry.date}</td>
                          <td>{entry.inputTokens.toLocaleString()}</td>
                          <td>{entry.outputTokens.toLocaleString()}</td>
                          <td>{entry.requests}</td>
                          <td>${cost}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state">
                  <p>暂无使用记录</p>
                </div>
              )}
            </>
          )}
        </section>
      </main>
    </>
  );
}

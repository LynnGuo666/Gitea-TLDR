import Head from 'next/head';
import { useMemo } from 'react';
import { UsageIcon } from '../components/icons';

const USD_PER_MILLION = 15;

export default function UsagePage() {
  const usageHistory = useMemo(
    () => [
      { label: '核心仓库', tokens: 82000, requests: 24 },
      { label: '移动端', tokens: 56000, requests: 19 },
      { label: '数据平台', tokens: 41000, requests: 12 },
    ],
    []
  );

  const totalTokens = useMemo(
    () => usageHistory.reduce((sum, item) => sum + item.tokens, 0),
    [usageHistory]
  );

  const totalRequests = useMemo(
    () => usageHistory.reduce((sum, item) => sum + item.requests, 0),
    [usageHistory]
  );

  const usdCost = useMemo(
    () => ((totalTokens / 1_000_000) * USD_PER_MILLION).toFixed(2),
    [totalTokens]
  );

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
            <div className="cost-pill">
              <span>预计美元</span>
              <strong>${usdCost}</strong>
            </div>
          </div>
          <div className="usage-summary">
            <div>
              <p>总 tokens</p>
              <strong>{totalTokens.toLocaleString()}</strong>
            </div>
            <div>
              <p>请求数</p>
              <strong>{totalRequests.toLocaleString()}</strong>
            </div>
            <div>
              <p>计费速率</p>
              <strong>${USD_PER_MILLION} / 1M tokens</strong>
            </div>
          </div>
          <table className="usage-table">
            <thead>
              <tr>
                <th>审查范围</th>
                <th>Tokens</th>
                <th>请求</th>
                <th>美刀</th>
              </tr>
            </thead>
            <tbody>
              {usageHistory.map((entry) => {
                const usd =
                  ((entry.tokens / 1_000_000) * USD_PER_MILLION).toFixed(2);
                return (
                  <tr key={entry.label}>
                    <td>{entry.label}</td>
                    <td>{entry.tokens.toLocaleString()}</td>
                    <td>{entry.requests}</td>
                    <td>${usd}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </main>
    </>
  );
}

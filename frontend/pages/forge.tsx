import Head from 'next/head';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import { useApiFetch } from '../lib/hooks';
import { ProviderRunSummary } from '../lib/types';

export default function ProviderRunsPage() {
  const { data, loading, error, refresh } = useApiFetch<{ runs: ProviderRunSummary[] }>(
    '/api/v2/provider-runs?provider=forge&limit=50&offset=0'
  );
  const runs = data?.runs || [];

  return (
    <>
      <Head><title>Provider Runs - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Provider Runs" subtitle="Provider 执行明细，默认展示 forge" />
        <div className="mt-4 grid gap-3">
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={refresh} className="text-sm text-primary hover:underline">重试</button>} />
          ) : runs.length === 0 ? (
            <EmptyState title="暂无 Provider 执行记录" description="尚未产生 forge 执行明细。" />
          ) : (
            runs.map((run) => (
              <div key={run.id} className="border-b border-divider py-3">
                <div className="font-medium">{run.provider_session_id}</div>
                <div className="text-sm text-default-500">{run.repo_full_name || '未关联仓库'} · {run.scenario} · {run.status} · {run.model || 'model unknown'}</div>
                <div className="text-xs text-default-400">tokens {run.input_tokens}/{run.output_tokens} · turns {run.turns} · tools {run.tool_calls_count}</div>
                {run.error_message && <div className="mt-1 text-sm text-danger">{run.error_message}</div>}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

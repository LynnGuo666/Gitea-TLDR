import Head from 'next/head';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import { useApiFetch } from '../lib/hooks';
import { UsageResponse } from '../lib/types';

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
}

export default function UsagePage() {
  const { data, loading, error, refresh } = useApiFetch<UsageResponse>('/api/v2/usage');

  return (
    <>
      <Head><title>Usage - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Usage" subtitle="Provider 与 Gitea 用量事件" />
        {loading ? (
          <div className="mt-4 text-sm text-default-400">加载中…</div>
        ) : error ? (
          <ErrorState className="mt-4" message={error} action={<button onClick={refresh} className="text-sm text-primary hover:underline">重试</button>} />
        ) : data ? (
          <>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Input</div><div className="text-2xl font-semibold">{formatNumber(data.summary.total_input_tokens)}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Output</div><div className="text-2xl font-semibold">{formatNumber(data.summary.total_output_tokens)}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Provider Calls</div><div className="text-2xl font-semibold">{data.summary.total_provider_calls}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Events</div><div className="text-2xl font-semibold">{data.summary.record_count}</div></div>
            </div>
            <div className="mt-6 grid gap-2">
              {data.events.length === 0 ? (
                <EmptyState title="暂无用量事件" description="尚未产生 token / API 调用记录。" />
              ) : (
                data.events.map((event) => (
                  <div key={event.id} className="flex items-center justify-between border-b border-divider py-2 text-sm">
                    <span>{event.event_date} · repo {event.repository_id} · {event.provider || 'provider'}</span>
                    <span>{event.input_tokens}/{event.output_tokens}</span>
                  </div>
                ))
              )}
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}

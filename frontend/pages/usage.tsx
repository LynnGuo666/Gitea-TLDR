import Head from 'next/head';
import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { apiFetch } from '../lib/api';
import { UsageResponse } from '../lib/types';

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);

  useEffect(() => {
    apiFetch('/api/v2/usage')
      .then((res) => res.json())
      .then((data) => setUsage(data))
      .catch(() => setUsage(null));
  }, []);

  return (
    <>
      <Head><title>Usage - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Usage" subtitle="Provider 与 Gitea 用量事件" />
        {usage && (
          <>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Input</div><div className="text-2xl font-semibold">{usage.summary.total_input_tokens}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Output</div><div className="text-2xl font-semibold">{usage.summary.total_output_tokens}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Provider Calls</div><div className="text-2xl font-semibold">{usage.summary.total_provider_calls}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Events</div><div className="text-2xl font-semibold">{usage.summary.record_count}</div></div>
            </div>
            <div className="mt-6 grid gap-2">
              {usage.events.map((event) => (
                <div key={event.id} className="flex items-center justify-between border-b border-divider py-2 text-sm">
                  <span>{event.event_date} · repo {event.repository_id} · {event.provider || 'provider'}</span>
                  <span>{event.input_tokens}/{event.output_tokens}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

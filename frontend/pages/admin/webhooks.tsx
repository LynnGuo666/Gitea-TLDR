import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button } from '@heroui/react';
import PageHeader from '../../components/PageHeader';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import { apiFetch } from '../../lib/api';

type WebhookEvent = {
  id: number;
  request_id: string;
  repository_id: number | null;
  event_type: string;
  status: string;
  error_message: string | null;
  retry_count: number;
  created_at: string | null;
};

export default function AdminWebhooksPage() {
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/v2/webhook-events?limit=100');
      if (!res.ok) throw new Error('加载失败');
      setEvents((await res.json()).events || []);
    } catch {
      setError('加载 webhook 事件失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const replay = async (id: number) => {
    const res = await apiFetch(`/api/v2/webhook-events/${id}/replay`, { method: 'POST' });
    if (res.ok) await load();
  };

  return (
    <>
      <Head><title>Webhook Events - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Webhook Events" subtitle="Webhook 处理记录与重放" />
        <div className="mt-4 grid gap-3">
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={load} className="text-sm text-primary hover:underline">重试</button>} />
          ) : events.length === 0 ? (
            <EmptyState title="暂无 Webhook 事件" description="尚未收到任何 webhook 事件记录。" />
          ) : (
            events.map((event) => (
              <div key={event.id} className="flex items-center justify-between border-b border-divider py-3">
                <div>
                  <div className="font-medium">{event.event_type} · {event.request_id}</div>
                  <div className="text-sm text-default-500">repo {event.repository_id || 'n/a'} · {event.status} · retry {event.retry_count}</div>
                  {event.error_message && <div className="text-sm text-danger">{event.error_message}</div>}
                </div>
                <Button size="sm" variant="flat" onPress={() => replay(event.id)}>重放</Button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

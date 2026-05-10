import Head from 'next/head';
import { useEffect, useState } from 'react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';
import { AuditEvent, UsageResponse } from '../../lib/types';

export default function AdminDashboard() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [audits, setAudits] = useState<AuditEvent[]>([]);

  useEffect(() => {
    Promise.all([apiFetch('/api/v2/usage'), apiFetch('/api/v2/audit-events?limit=10')])
      .then(async ([usageRes, auditRes]) => {
        if (usageRes.ok) setUsage(await usageRes.json());
        if (auditRes.ok) setAudits((await auditRes.json()).events || []);
      })
      .catch(() => undefined);
  }, []);

  return (
    <>
      <Head><title>Admin - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Admin" subtitle="当前 schema 的运行概览与审计事件" />
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Usage Events</div><div className="text-2xl font-semibold">{usage?.summary.record_count ?? 0}</div></div>
          <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Input Tokens</div><div className="text-2xl font-semibold">{usage?.summary.total_input_tokens ?? 0}</div></div>
          <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Output Tokens</div><div className="text-2xl font-semibold">{usage?.summary.total_output_tokens ?? 0}</div></div>
        </div>
        <div className="mt-6 grid gap-2">
          {audits.map((event) => (
            <div key={event.id} className="border-b border-divider py-2 text-sm">
              {event.created_at} · {event.action} · {event.resource_type} · {event.status}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

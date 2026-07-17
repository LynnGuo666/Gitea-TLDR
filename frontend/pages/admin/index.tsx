import Head from 'next/head';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { BarChart3, GitBranch, Users, Webhook, Settings, BookOpen, Lightbulb } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import { apiFetch } from '../../lib/api';
import { AuditEvent, UsageResponse } from '../../lib/types';

type AdminSubPage = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

const ADMIN_SUB_PAGES: AdminSubPage[] = [
  { href: '/admin/repos', label: '仓库', description: '已注册仓库列表', icon: GitBranch },
  { href: '/admin/users', label: '用户', description: 'Actor 与角色管理', icon: Users },
  { href: '/admin/webhooks', label: 'Webhook 事件', description: '事件处理记录与重放', icon: Webhook },
  { href: '/admin/config', label: '应用设置', description: 'app_settings 管理', icon: Settings },
  { href: '/admin/reviews', label: '审查记录', description: '全部 PR 审查运行', icon: BookOpen },
  { href: '/admin/issues', label: 'Issue 分析', description: '全部 Issue 分析运行', icon: Lightbulb },
];

export default function AdminDashboard() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [audits, setAudits] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [usageRes, auditRes] = await Promise.all([
        apiFetch('/api/v2/usage'),
        apiFetch('/api/v2/audit-events?limit=10'),
      ]);
      if (usageRes.ok) setUsage(await usageRes.json());
      if (auditRes.ok) setAudits((await auditRes.json()).events || []);
    } catch {
      setError('加载管理概览失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  return (
    <>
      <Head><title>Admin - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Admin" subtitle="运行概览与子页面入口" />

        <section className="mt-6">
          <h2 className="m-0 text-lg font-semibold mb-3">管理子页面</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {ADMIN_SUB_PAGES.map(({ href, label, description, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="no-underline rounded-xl border border-divider p-4 hover:border-primary/50 hover:bg-default-100/60 transition-colors flex items-start gap-3"
              >
                <span className="w-9 h-9 rounded-lg bg-default-100 flex items-center justify-center text-default-500 shrink-0">
                  <Icon size={18} />
                </span>
                <div className="min-w-0">
                  <p className="m-0 font-medium text-sm text-foreground">{label}</p>
                  <p className="m-0 text-xs text-default-500 mt-0.5">{description}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        <section className="mt-8">
          <h2 className="m-0 text-lg font-semibold mb-3 flex items-center gap-2">
            <BarChart3 size={18} /> 用量概览
          </h2>
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={load} className="text-sm text-primary hover:underline">重试</button>} />
          ) : (
            <div className="grid gap-3 md:grid-cols-3">
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Usage Events</div><div className="text-2xl font-semibold">{usage?.summary.record_count ?? 0}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Input Tokens</div><div className="text-2xl font-semibold">{usage?.summary.total_input_tokens ?? 0}</div></div>
              <div className="border-b border-divider py-3"><div className="text-sm text-default-500">Output Tokens</div><div className="text-2xl font-semibold">{usage?.summary.total_output_tokens ?? 0}</div></div>
            </div>
          )}
        </section>

        <section className="mt-8">
          <h2 className="m-0 text-lg font-semibold mb-3">最近审计事件</h2>
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? null : audits.length === 0 ? (
            <EmptyState title="暂无审计事件" description="尚未记录任何写操作审计。" />
          ) : (
            <div className="grid gap-2">
              {audits.map((event) => (
                <div key={event.id} className="border-b border-divider py-2 text-sm">
                  {event.created_at} · {event.action} · {event.resource_type} · {event.status}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}

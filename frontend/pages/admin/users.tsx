import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button, Select, SelectItem } from '@heroui/react';
import PageHeader from '../../components/PageHeader';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import { apiFetch } from '../../lib/api';
import { Actor } from '../../lib/types';

export default function AdminActorsPage() {
  const [actors, setActors] = useState<Actor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/v2/actors');
      if (!res.ok) throw new Error('加载失败');
      setActors((await res.json()).actors || []);
    } catch {
      setError('加载用户列表失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const updateRole = async (actor: Actor, role: string) => {
    const res = await apiFetch(`/api/v2/actors/${actor.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    if (res.ok) await load();
  };

  const toggleActive = async (actor: Actor) => {
    const res = await apiFetch(`/api/v2/actors/${actor.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !actor.is_active }),
    });
    if (res.ok) await load();
  };

  return (
    <>
      <Head><title>Actors - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Actors" subtitle="当前 actors 管理" />
        <div className="mt-4 grid gap-3">
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={load} className="text-sm text-primary hover:underline">重试</button>} />
          ) : actors.length === 0 ? (
            <EmptyState title="暂无用户" description="尚未有任何 actor 记录。" />
          ) : (
            actors.map((actor) => (
              <div key={actor.id} className="flex items-center justify-between border-b border-divider py-3">
                <div>
                  <div className="font-medium">{actor.external_username}</div>
                  <div className="text-sm text-default-500">{actor.external_provider} · {actor.role} · {actor.is_active ? 'active' : 'disabled'}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Select size="sm" className="w-36" selectedKeys={new Set([actor.role])} onSelectionChange={(keys) => updateRole(actor, String(Array.from(keys)[0] || actor.role))}>
                    {['user', 'admin', 'super_admin'].map((role) => <SelectItem key={role}>{role}</SelectItem>)}
                  </Select>
                  <Button size="sm" variant="flat" onPress={() => toggleActive(actor)}>{actor.is_active ? '禁用' : '启用'}</Button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

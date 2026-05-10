import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button, Select, SelectItem } from '@heroui/react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';
import { Actor } from '../../lib/types';

export default function AdminActorsPage() {
  const [actors, setActors] = useState<Actor[]>([]);

  const load = async () => {
    const res = await apiFetch('/api/v2/actors');
    if (res.ok) setActors((await res.json()).actors || []);
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
          {actors.map((actor) => (
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
          ))}
        </div>
      </div>
    </>
  );
}

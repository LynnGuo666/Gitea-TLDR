import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button, Input, Textarea } from '@heroui/react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';
import { AppSetting } from '../../lib/types';

export default function AdminConfigPage() {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [form, setForm] = useState({ key: '', category: 'general', value: '', description: '' });

  const load = async () => {
    const res = await apiFetch('/api/v2/app-settings');
    if (res.ok) setSettings((await res.json()).settings || []);
  };

  useEffect(() => { void load(); }, []);

  const save = async () => {
    const parsed = (() => {
      try { return JSON.parse(form.value); } catch { return form.value; }
    })();
    const res = await apiFetch(`/api/v2/app-settings/${encodeURIComponent(form.key)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value: parsed, category: form.category, description: form.description || null }),
    });
    if (res.ok) {
      setForm({ key: '', category: 'general', value: '', description: '' });
      await load();
    }
  };

  const remove = async (key: string) => {
    const res = await apiFetch(`/api/v2/app-settings/${encodeURIComponent(key)}`, { method: 'DELETE' });
    if (res.ok) await load();
  };

  return (
    <>
      <Head><title>App Settings - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="App Settings" subtitle="当前 app_settings 管理" />
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <Input label="Key" value={form.key} onValueChange={(key) => setForm({ ...form, key })} />
          <Input label="Category" value={form.category} onValueChange={(category) => setForm({ ...form, category })} />
          <Input label="Description" value={form.description} onValueChange={(description) => setForm({ ...form, description })} />
        </div>
        <Textarea className="mt-3" label="Value JSON 或字符串" value={form.value} onValueChange={(value) => setForm({ ...form, value })} />
        <Button className="mt-3" color="primary" onPress={save} isDisabled={!form.key}>保存设置</Button>
        <div className="mt-6 grid gap-2">
          {settings.map((setting) => (
            <div key={setting.id} className="flex items-center justify-between border-b border-divider py-2 text-sm">
              <span>{setting.category} · {setting.key} · {JSON.stringify(setting.value)}</span>
              <Button size="sm" color="danger" variant="light" onPress={() => remove(setting.key)}>删除</Button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

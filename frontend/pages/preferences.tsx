import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button, Input } from '@heroui/react';
import PageHeader from '../components/PageHeader';
import SectionHeader from '../components/SectionHeader';
import { apiFetch } from '../lib/api';
import { ProviderCredential } from '../lib/types';

export default function PreferencesPage() {
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [credentialForm, setCredentialForm] = useState({ name: '', provider: 'anthropic', api_url: '', api_key: '' });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const credRes = await apiFetch('/api/v2/provider-credentials');
    if (credRes.ok) setCredentials((await credRes.json()).credentials || []);
    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  const createCredential = async () => {
    const res = await apiFetch('/api/v2/provider-credentials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: credentialForm.name,
        provider: credentialForm.provider,
        api_url: credentialForm.api_url || null,
        api_key: credentialForm.api_key || null,
      }),
    });
    if (res.ok) {
      setCredentialForm({ name: '', provider: 'anthropic', api_url: '', api_key: '' });
      await load();
    }
  };

  const rotateCredential = async (id: number) => {
    const apiKey = window.prompt('输入新的 API Key');
    if (!apiKey) return;
    const res = await apiFetch(`/api/v2/provider-credentials/${id}/rotate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey }),
    });
    if (res.ok) await load();
  };

  const deleteCredential = async (id: number) => {
    const res = await apiFetch(`/api/v2/provider-credentials/${id}`, { method: 'DELETE' });
    if (res.ok) await load();
  };

  return (
    <>
      <Head>
        <title>偏好设置 - Gitea TLDR</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-8">
        <PageHeader title="偏好设置" subtitle="管理 Provider 凭证" />

        <section className="border-t border-divider pt-5">
          <SectionHeader title="Provider 凭证" />
          <div className="grid gap-3 md:grid-cols-4 mt-4">
            <Input label="名称" value={credentialForm.name} onValueChange={(name) => setCredentialForm({ ...credentialForm, name })} />
            <Input label="Provider" value={credentialForm.provider} onValueChange={(provider) => setCredentialForm({ ...credentialForm, provider })} />
            <Input
              label="API URL"
              placeholder="https://api.anthropic.com"
              value={credentialForm.api_url}
              onValueChange={(api_url) => setCredentialForm({ ...credentialForm, api_url })}
            />
            <Input
              label="Forge / Anthropic API Key"
              type="password"
              value={credentialForm.api_key}
              onValueChange={(api_key) => setCredentialForm({ ...credentialForm, api_key })}
            />
          </div>
          <Button className="mt-3" color="primary" onPress={createCredential} isDisabled={!credentialForm.name || loading}>
            新建凭证
          </Button>
          <div className="mt-5 grid gap-3">
            {credentials.map((credential) => (
              <div key={credential.id} className="flex items-center justify-between border-b border-divider py-3">
                <div>
                  <div className="font-medium">{credential.name}</div>
                  <div className="text-sm text-default-500">{credential.provider} · {credential.api_url || '默认 API'} · {credential.has_api_key ? '已保存 Key' : '未保存 Key'}</div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="flat" onPress={() => rotateCredential(credential.id)}>轮换</Button>
                  <Button size="sm" color="danger" variant="light" onPress={() => deleteCredential(credential.id)}>删除</Button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

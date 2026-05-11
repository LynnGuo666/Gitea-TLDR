import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { Button, Chip, Input, Select, SelectItem, Textarea } from '@heroui/react';
import PageHeader from '../../../components/PageHeader';
import SectionHeader from '../../../components/SectionHeader';
import { apiFetch } from '../../../lib/api';
import { ProviderCredential, RepositoryConfiguration } from '../../../lib/types';

type Scenario = 'review' | 'issue';

export default function RepoPage() {
  const router = useRouter();
  const owner = String(router.query.owner || '');
  const repo = String(router.query.repo || '');
  const [scenario, setScenario] = useState<Scenario>('review');
  const [config, setConfig] = useState<RepositoryConfiguration | null>(null);
  const [configurationRequired, setConfigurationRequired] = useState(false);
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [hasAdmin, setHasAdmin] = useState<boolean | null>(null);
  const [permissionsLoading, setPermissionsLoading] = useState(true);
  const [form, setForm] = useState({
    engine: '',
    model: '',
    credential_id: '',
    wire_api: '',
    temperature: '',
    max_tokens: '',
    custom_prompt: '',
    focus: '',
    features: '',
    is_active: true,
  });

  const isReadOnly = hasAdmin === false;

  const loadStatic = async () => {
    const credentialRes = await apiFetch('/api/v2/provider-credentials');
    if (credentialRes.ok) setCredentials((await credentialRes.json()).credentials || []);
  };

  const loadPermissions = async () => {
    if (!owner || !repo) return;
    setPermissionsLoading(true);
    try {
      const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/permissions`);
      if (res.ok) {
        const perms = await res.json();
        setHasAdmin(perms.admin ?? false);
      } else {
        setHasAdmin(null);
      }
    } catch {
      setHasAdmin(null);
    } finally {
      setPermissionsLoading(false);
    }
  };

  const loadConfig = async () => {
    if (!owner || !repo) return;
    const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/configurations?scenario=${scenario}`);
    if (res.status === 404) {
      setConfig(null);
      setConfigurationRequired(true);
      return;
    }
    if (!res.ok) return;
    const data = (await res.json()) as RepositoryConfiguration;
    setConfig(data);
    setConfigurationRequired(false);
    setForm({
      engine: data.engine || '',
      model: data.model || '',
      credential_id: data.credential_id ? String(data.credential_id) : '',
      wire_api: data.wire_api || '',
      temperature: data.temperature == null ? '' : String(data.temperature),
      max_tokens: data.max_tokens == null ? '' : String(data.max_tokens),
      custom_prompt: data.custom_prompt || '',
      focus: data.focus.join(','),
      features: data.features.join(','),
      is_active: data.is_active,
    });
  };

  useEffect(() => {
    if (!router.isReady) return;
    void loadStatic();
    void loadPermissions();
  }, [router.isReady]);

  useEffect(() => {
    if (!router.isReady) return;
    void loadConfig();
  }, [router.isReady, owner, repo, scenario]);

  const saveConfig = async () => {
    const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/configurations/${scenario}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        engine: form.engine || undefined,
        model: form.model || null,
        credential_id: form.credential_id ? Number(form.credential_id) : null,
        wire_api: form.wire_api || null,
        temperature: form.temperature ? Number(form.temperature) : null,
        max_tokens: form.max_tokens ? Number(form.max_tokens) : null,
        custom_prompt: form.custom_prompt || null,
        focus: form.focus.split(',').map((item) => item.trim()).filter(Boolean),
        features: form.features.split(',').map((item) => item.trim()).filter(Boolean),
        is_active: form.is_active,
      }),
    });
    if (res.ok) await loadConfig();
  };

  return (
    <>
      <Head>
        <title>{owner}/{repo} - 仓库配置</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-8">
        <PageHeader title={`${owner}/${repo}`} subtitle="仓库独立配置，运行时不会从全局 fallback" />

        {isReadOnly && (
          <div className="rounded-md border border-default-300 bg-default-50 p-4 text-sm text-default-600 flex items-center gap-3">
            <Chip size="sm" variant="flat" color="default">只读</Chip>
            你没有此仓库的管理权限，配置为只读查看。如需修改请联系仓库管理员。
          </div>
        )}

        <section className="border-t border-divider pt-5">
          <div className="flex items-center justify-between gap-3">
            <SectionHeader title="场景配置" />
            <Select className="max-w-48" selectedKeys={new Set([scenario])} onSelectionChange={(keys) => setScenario(String(Array.from(keys)[0] || 'review') as Scenario)}>
              <SelectItem key="review">review</SelectItem>
              <SelectItem key="issue">issue</SelectItem>
            </Select>
          </div>

          {permissionsLoading ? (
            <div className="mt-6 text-sm text-default-400">加载权限…</div>
          ) : configurationRequired ? (
            <div className="mt-6 rounded-md border border-warning/50 bg-warning/10 p-4 text-sm text-warning-700">
              configuration_required：这个仓库还没有 {scenario} 配置，请联系管理员初始化。
            </div>
          ) : config ? (
            <div className="mt-6 flex flex-col gap-4">
              <div className="grid gap-3 md:grid-cols-3">
                <Input label="Engine" value={form.engine} isDisabled={isReadOnly} onValueChange={(engine) => setForm({ ...form, engine })} />
                <Input label="Model" value={form.model} isDisabled={isReadOnly} onValueChange={(model) => setForm({ ...form, model })} />
                <Select label="凭证" isDisabled={isReadOnly} selectedKeys={form.credential_id ? new Set([form.credential_id]) : new Set([])} onSelectionChange={(keys) => setForm({ ...form, credential_id: String(Array.from(keys)[0] || '') })}>
                  {credentials.map((credential) => <SelectItem key={String(credential.id)}>{credential.name}</SelectItem>)}
                </Select>
                <Input label="Wire API" value={form.wire_api} isDisabled={isReadOnly} onValueChange={(wire_api) => setForm({ ...form, wire_api })} />
                <Input label="Temperature" value={form.temperature} isDisabled={isReadOnly} onValueChange={(temperature) => setForm({ ...form, temperature })} />
                <Input label="Max tokens" value={form.max_tokens} isDisabled={isReadOnly} onValueChange={(max_tokens) => setForm({ ...form, max_tokens })} />
              </div>
              <Textarea label="Focus，逗号分隔" value={form.focus} isDisabled={isReadOnly} onValueChange={(focus) => setForm({ ...form, focus })} />
              <Textarea label="Features，逗号分隔" value={form.features} isDisabled={isReadOnly} onValueChange={(features) => setForm({ ...form, features })} />
              <Textarea label="Custom prompt" value={form.custom_prompt} isDisabled={isReadOnly} onValueChange={(custom_prompt) => setForm({ ...form, custom_prompt })} />
              <Button color="primary" onPress={saveConfig} isDisabled={isReadOnly}>保存仓库配置</Button>
            </div>
          ) : null}
        </section>
      </div>
    </>
  );
}

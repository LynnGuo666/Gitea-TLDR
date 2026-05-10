import Head from 'next/head';
import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { Button, Input, Select, SelectItem, Textarea } from '@heroui/react';
import PageHeader from '../../../components/PageHeader';
import SectionHeader from '../../../components/SectionHeader';
import { apiFetch } from '../../../lib/api';
import { ConfigTemplate, ProviderCredential, RepositoryConfiguration } from '../../../lib/types';

type Scenario = 'review' | 'issue';

function isTemplateBehind(config: RepositoryConfiguration | null, template: ConfigTemplate | undefined) {
  if (!config?.template_version_copied_at || !template?.updated_at) return false;
  return new Date(template.updated_at).getTime() > new Date(config.template_version_copied_at).getTime();
}

export default function RepoPage() {
  const router = useRouter();
  const owner = String(router.query.owner || '');
  const repo = String(router.query.repo || '');
  const [scenario, setScenario] = useState<Scenario>('review');
  const [config, setConfig] = useState<RepositoryConfiguration | null>(null);
  const [configurationRequired, setConfigurationRequired] = useState(false);
  const [templates, setTemplates] = useState<ConfigTemplate[]>([]);
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
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

  const scenarioTemplates = useMemo(() => templates.filter((item) => item.scenario === scenario), [templates, scenario]);
  const sourceTemplate = templates.find((item) => item.id === config?.source_template_id);
  const behindTemplate = isTemplateBehind(config, sourceTemplate);

  const loadStatic = async () => {
    const [templateRes, credentialRes] = await Promise.all([
      apiFetch('/api/v2/config-templates'),
      apiFetch('/api/v2/provider-credentials'),
    ]);
    if (templateRes.ok) setTemplates((await templateRes.json()).templates || []);
    if (credentialRes.ok) setCredentials((await credentialRes.json()).credentials || []);
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
  }, [router.isReady]);

  useEffect(() => {
    if (!router.isReady) return;
    void loadConfig();
  }, [router.isReady, owner, repo, scenario]);

  const createFromTemplate = async () => {
    const templateId = selectedTemplateId || scenarioTemplates.find((item) => item.is_default)?.id || scenarioTemplates[0]?.id;
    if (!templateId) return;
    const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/configurations/from-template`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, template_id: Number(templateId) }),
    });
    if (res.ok) await loadConfig();
  };

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

  const applyTemplate = async () => {
    const templateId = selectedTemplateId || config?.source_template_id;
    if (!templateId) return;
    const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/configurations/${scenario}/apply-template`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: Number(templateId) }),
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

        <section className="border-t border-divider pt-5">
          <div className="flex items-center justify-between gap-3">
            <SectionHeader title="场景配置" />
            <Select className="max-w-48" selectedKeys={new Set([scenario])} onSelectionChange={(keys) => setScenario(String(Array.from(keys)[0] || 'review') as Scenario)}>
              <SelectItem key="review">review</SelectItem>
              <SelectItem key="issue">issue</SelectItem>
            </Select>
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-3">
            <Select label="模板" className="max-w-xs" selectedKeys={selectedTemplateId ? new Set([selectedTemplateId]) : new Set([])} onSelectionChange={(keys) => setSelectedTemplateId(String(Array.from(keys)[0] || ''))}>
              {scenarioTemplates.map((template) => <SelectItem key={String(template.id)}>{template.name}</SelectItem>)}
            </Select>
            {configurationRequired ? (
              <Button color="primary" onPress={createFromTemplate} isDisabled={!scenarioTemplates.length}>从模板初始化配置</Button>
            ) : (
              <Button variant="flat" onPress={applyTemplate} isDisabled={!selectedTemplateId && !config?.source_template_id}>应用模板</Button>
            )}
          </div>

          {configurationRequired ? (
            <div className="mt-6 rounded-md border border-warning/50 bg-warning/10 p-4 text-sm text-warning-700">
              configuration_required：这个仓库还没有 {scenario} 配置，请先从模板初始化。
            </div>
          ) : config ? (
            <div className="mt-6 flex flex-col gap-4">
              <div className="grid gap-3 md:grid-cols-3">
                <Input label="Engine" value={form.engine} onValueChange={(engine) => setForm({ ...form, engine })} />
                <Input label="Model" value={form.model} onValueChange={(model) => setForm({ ...form, model })} />
                <Select label="凭证" selectedKeys={form.credential_id ? new Set([form.credential_id]) : new Set([])} onSelectionChange={(keys) => setForm({ ...form, credential_id: String(Array.from(keys)[0] || '') })}>
                  {credentials.map((credential) => <SelectItem key={String(credential.id)}>{credential.name}</SelectItem>)}
                </Select>
                <Input label="Wire API" value={form.wire_api} onValueChange={(wire_api) => setForm({ ...form, wire_api })} />
                <Input label="Temperature" value={form.temperature} onValueChange={(temperature) => setForm({ ...form, temperature })} />
                <Input label="Max tokens" value={form.max_tokens} onValueChange={(max_tokens) => setForm({ ...form, max_tokens })} />
              </div>
              <Textarea label="Focus，逗号分隔" value={form.focus} onValueChange={(focus) => setForm({ ...form, focus })} />
              <Textarea label="Features，逗号分隔" value={form.features} onValueChange={(features) => setForm({ ...form, features })} />
              <Textarea label="Custom prompt" value={form.custom_prompt} onValueChange={(custom_prompt) => setForm({ ...form, custom_prompt })} />
              <div className="text-sm text-default-500">
                模板 #{config.source_template_id || '无'} · 复制时间 {config.template_version_copied_at || '未知'} · {behindTemplate ? '落后模板' : '与模板同步或无模板版本'}
              </div>
              <Button color="primary" onPress={saveConfig}>保存仓库配置</Button>
            </div>
          ) : null}
        </section>
      </div>
    </>
  );
}

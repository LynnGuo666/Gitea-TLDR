import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button, Input, Select, SelectItem, Textarea } from '@heroui/react';
import PageHeader from '../components/PageHeader';
import SectionHeader from '../components/SectionHeader';
import { apiFetch } from '../lib/api';
import { ConfigTemplate, ProviderCredential } from '../lib/types';

const scenarios = ['review', 'issue'];

export default function PreferencesPage() {
  const [credentials, setCredentials] = useState<ProviderCredential[]>([]);
  const [templates, setTemplates] = useState<ConfigTemplate[]>([]);
  const [credentialForm, setCredentialForm] = useState({ name: '', provider: 'anthropic', api_url: '', api_key: '' });
  const [templateForm, setTemplateForm] = useState({
    scenario: 'review',
    name: '',
    engine: 'claude_code',
    model: '',
    credential_id: '',
    wire_api: '',
    temperature: '',
    max_tokens: '',
    custom_prompt: '',
    focus: '',
    features: 'comment',
    is_default: false,
  });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [credRes, tmplRes] = await Promise.all([
      apiFetch('/api/v2/provider-credentials'),
      apiFetch('/api/v2/config-templates'),
    ]);
    if (credRes.ok) setCredentials((await credRes.json()).credentials || []);
    if (tmplRes.ok) setTemplates((await tmplRes.json()).templates || []);
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

  const createTemplate = async () => {
    const res = await apiFetch('/api/v2/config-templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario: templateForm.scenario,
        name: templateForm.name,
        engine: templateForm.engine,
        model: templateForm.model || null,
        credential_id: templateForm.credential_id ? Number(templateForm.credential_id) : null,
        wire_api: templateForm.wire_api || null,
        temperature: templateForm.temperature ? Number(templateForm.temperature) : null,
        max_tokens: templateForm.max_tokens ? Number(templateForm.max_tokens) : null,
        custom_prompt: templateForm.custom_prompt || null,
        focus: templateForm.focus.split(',').map((item) => item.trim()).filter(Boolean),
        features: templateForm.features.split(',').map((item) => item.trim()).filter(Boolean),
        is_default: templateForm.is_default,
      }),
    });
    if (res.ok) {
      setTemplateForm({ ...templateForm, name: '', model: '', custom_prompt: '' });
      await load();
    }
  };

  const deleteTemplate = async (id: number) => {
    const res = await apiFetch(`/api/v2/config-templates/${id}`, { method: 'DELETE' });
    if (res.ok) await load();
  };

  return (
    <>
      <Head>
        <title>配置模板 - Gitea TLDR</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-8">
        <PageHeader title="配置模板" subtitle="管理 Provider 凭证与可复制到仓库的配置模板" />

        <section className="border-t border-divider pt-5">
          <SectionHeader title="Provider 凭证" />
          <div className="grid gap-3 md:grid-cols-4 mt-4">
            <Input label="名称" value={credentialForm.name} onValueChange={(name) => setCredentialForm({ ...credentialForm, name })} />
            <Input label="Provider" value={credentialForm.provider} onValueChange={(provider) => setCredentialForm({ ...credentialForm, provider })} />
            <Input label="API URL" value={credentialForm.api_url} onValueChange={(api_url) => setCredentialForm({ ...credentialForm, api_url })} />
            <Input label="API Key" type="password" value={credentialForm.api_key} onValueChange={(api_key) => setCredentialForm({ ...credentialForm, api_key })} />
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

        <section className="border-t border-divider pt-5">
          <SectionHeader title="配置模板" />
          <div className="grid gap-3 md:grid-cols-3 mt-4">
            <Select label="场景" selectedKeys={new Set([templateForm.scenario])} onSelectionChange={(keys) => setTemplateForm({ ...templateForm, scenario: String(Array.from(keys)[0] || 'review') })}>
              {scenarios.map((scenario) => <SelectItem key={scenario}>{scenario}</SelectItem>)}
            </Select>
            <Input label="模板名称" value={templateForm.name} onValueChange={(name) => setTemplateForm({ ...templateForm, name })} />
            <Input label="Engine" value={templateForm.engine} onValueChange={(engine) => setTemplateForm({ ...templateForm, engine })} />
            <Input label="Model" value={templateForm.model} onValueChange={(model) => setTemplateForm({ ...templateForm, model })} />
            <Select label="凭证" selectedKeys={templateForm.credential_id ? new Set([templateForm.credential_id]) : new Set([])} onSelectionChange={(keys) => setTemplateForm({ ...templateForm, credential_id: String(Array.from(keys)[0] || '') })}>
              {credentials.map((credential) => <SelectItem key={String(credential.id)}>{credential.name}</SelectItem>)}
            </Select>
            <Input label="Wire API" value={templateForm.wire_api} onValueChange={(wire_api) => setTemplateForm({ ...templateForm, wire_api })} />
            <Input label="Temperature" value={templateForm.temperature} onValueChange={(temperature) => setTemplateForm({ ...templateForm, temperature })} />
            <Input label="Max tokens" value={templateForm.max_tokens} onValueChange={(max_tokens) => setTemplateForm({ ...templateForm, max_tokens })} />
            <Input label="Features" value={templateForm.features} onValueChange={(features) => setTemplateForm({ ...templateForm, features })} />
          </div>
          <Textarea className="mt-3" label="Focus，逗号分隔" value={templateForm.focus} onValueChange={(focus) => setTemplateForm({ ...templateForm, focus })} />
          <Textarea className="mt-3" label="Custom prompt" value={templateForm.custom_prompt} onValueChange={(custom_prompt) => setTemplateForm({ ...templateForm, custom_prompt })} />
          <Button className="mt-3" color="primary" onPress={createTemplate} isDisabled={!templateForm.name || loading}>
            新建模板
          </Button>
          <div className="mt-5 grid gap-3">
            {templates.map((template) => (
              <div key={template.id} className="flex items-center justify-between border-b border-divider py-3">
                <div>
                  <div className="font-medium">{template.name} <span className="text-xs text-default-500">/{template.scenario}</span></div>
                  <div className="text-sm text-default-500">{template.engine} · {template.model || '未指定模型'} · credential #{template.credential_id || '无'}</div>
                </div>
                <Button size="sm" color="danger" variant="light" onPress={() => deleteTemplate(template.id)}>删除</Button>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

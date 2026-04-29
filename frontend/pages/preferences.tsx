import Head from 'next/head';
import { useCallback, useContext, useEffect, useState } from 'react';
import { Button, Chip, Input, Select, SelectItem, addToast } from '@heroui/react';
import { Bot } from 'lucide-react';
import { AuthContext } from '../lib/auth';
import { apiFetch } from '../lib/api';
import PageHeader from '../components/PageHeader';
import SectionHeader from '../components/SectionHeader';
import { GlobalReviewConfig, ProviderInfo } from '../lib/types';

interface GlobalIssueConfig {
  configured: boolean;
  engine?: string;
  model?: string;
  api_url?: string;
  has_api_key?: boolean;
  custom_prompt?: string;
  default_focus?: string[];
}

export default function PreferencesPage() {
  const { status: authStatus } = useContext(AuthContext);
  const [globalProvider, setGlobalProvider] = useState<GlobalReviewConfig | null>(null);
  const [globalProviderLoading, setGlobalProviderLoading] = useState(true);
  const [globalProviderSaving, setGlobalProviderSaving] = useState(false);
  const [globalBaseUrl, setGlobalBaseUrl] = useState('');
  const [globalAuthToken, setGlobalAuthToken] = useState('');
  const [globalModel, setGlobalModel] = useState('');
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('claude_code');

  const [globalIssue, setGlobalIssue] = useState<GlobalIssueConfig | null>(null);
  const [globalIssueLoading, setGlobalIssueLoading] = useState(true);
  const [globalIssueSaving, setGlobalIssueSaving] = useState(false);
  const [globalIssueApiUrl, setGlobalIssueApiUrl] = useState('');
  const [globalIssueApiKey, setGlobalIssueApiKey] = useState('');
  const [globalIssueModel, setGlobalIssueModel] = useState('');
  const [globalIssueCustomPrompt, setGlobalIssueCustomPrompt] = useState('');

  const fetchGlobalProvider = useCallback(async () => {
    if (!authStatus.loggedIn) {
      setGlobalProvider(null);
      setGlobalProviderLoading(false);
      return;
    }

    setGlobalProviderLoading(true);
    try {
      const res = await apiFetch('/api/config/global?type=review');
      if (!res.ok) {
        setGlobalProvider(null);
        return;
      }
      const data: GlobalReviewConfig = await res.json();
      setGlobalProvider(data);
      setGlobalBaseUrl(data.api_url || '');
      setGlobalModel(data.model || '');
      if (data.engine) {
        setSelectedProvider(data.engine);
      }
    } catch (error) {
      console.error('Failed to fetch global provider config:', error);
      setGlobalProvider(null);
    } finally {
      setGlobalProviderLoading(false);
    }
  }, [authStatus.loggedIn]);

  const fetchGlobalIssue = useCallback(async () => {
    if (!authStatus.loggedIn) {
      setGlobalIssue(null);
      setGlobalIssueLoading(false);
      return;
    }

    setGlobalIssueLoading(true);
    try {
      const res = await apiFetch('/api/config/global?type=issue');
      if (!res.ok) {
        setGlobalIssue(null);
        return;
      }
      const data = await res.json();
      setGlobalIssue(data);
      setGlobalIssueApiUrl(data.api_url || '');
      setGlobalIssueModel(data.model || '');
      setGlobalIssueCustomPrompt(data.custom_prompt || '');
    } catch (error) {
      console.error('Failed to fetch global issue config:', error);
      setGlobalIssue(null);
    } finally {
      setGlobalIssueLoading(false);
    }
  }, [authStatus.loggedIn]);

  useEffect(() => {
    const fetchProviders = async () => {
      try {
        const res = await apiFetch('/api/providers');
        if (!res.ok) {
          return;
        }
        const data = await res.json();
        setProviders(data.providers || []);
      } catch {
        setProviders([]);
      }
    };

    fetchProviders();
    fetchGlobalProvider();
    fetchGlobalIssue();
  }, [fetchGlobalProvider, fetchGlobalIssue]);

  const saveGlobalReviewConfig = async () => {
    if (!authStatus.loggedIn) {
      addToast({ title: '请先登录后再配置', color: 'warning' });
      return;
    }

    if (selectedProvider === 'claude_code' && !globalBaseUrl.trim()) {
      addToast({ title: 'Claude Code 必须配置 Base URL', color: 'warning' });
      return;
    }

    setGlobalProviderSaving(true);
    try {
      const res = await apiFetch('/api/config/global?type=review', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine: selectedProvider,
          model: globalModel || null,
          api_url: globalBaseUrl || null,
          api_key: globalAuthToken || null,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        addToast({ title: data.detail || '保存失败', color: 'danger' });
        return;
      }

      addToast({ title: '个人设置已保存', color: 'success' });
      setGlobalAuthToken('');
      if (data.engine) {
        setSelectedProvider(data.engine);
      }
      setGlobalProvider({
        configured: !!(data.api_url || data.has_api_key),
        api_url: data.api_url,
        engine: data.engine,
        model: data.model,
        has_api_key: data.has_api_key,
      });
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setGlobalProviderSaving(false);
    }
  };

  const saveGlobalIssueConfig = async () => {
    if (!authStatus.loggedIn) {
      addToast({ title: '请先登录后再配置', color: 'warning' });
      return;
    }

    setGlobalIssueSaving(true);
    try {
      const res = await apiFetch('/api/config/global?type=issue', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine: 'forge',
          api_url: globalIssueApiUrl || null,
          api_key: globalIssueApiKey || null,
          model: globalIssueModel || null,
          custom_prompt: globalIssueCustomPrompt || null,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        addToast({ title: data.detail || '保存失败', color: 'danger' });
        return;
      }

      addToast({ title: '全局 Issue 配置已保存', color: 'success' });
      setGlobalIssueApiKey('');
      setGlobalIssue({
        configured: !!(data.api_url || data.has_api_key),
        api_url: data.api_url,
        engine: data.engine,
        model: data.model,
        has_api_key: data.has_api_key,
        custom_prompt: data.custom_prompt,
        default_focus: data.default_focus,
      });
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setGlobalIssueSaving(false);
    }
  };

  const providerPlaceholders: Record<string, { baseUrl: string; apiKey: string }> = {
    claude_code: {
      baseUrl: '必须填写 Claude API Base URL',
      apiKey: 'sk-ant-...',
    },
    codex_cli: {
      baseUrl: 'https://api.openai.com (留空使用默认)',
      apiKey: 'sk-...',
    },
  };

  const currentPlaceholders = providerPlaceholders[selectedProvider] || providerPlaceholders.claude_code;
  const modelPlaceholders: Record<string, string> = {
    claude_code: '例如: claude-3-7-sonnet-20250219',
    codex_cli: '例如: gpt-5.3-codex',
  };
  const currentModelPlaceholder = modelPlaceholders[selectedProvider] || '例如: gpt-5.3-codex';

  return (
    <>
      <Head>
        <title>个人设置 - LCPU AI Reviewer</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <div className="pb-4">
          <PageHeader title="个人设置" subtitle="维护全局 AI 审查默认引擎和凭据" />
        </div>

        <section className="py-5 border-t border-divider/60">
          <SectionHeader
            title="全局 AI 审查配置"
            icon={<Bot size={18} />}
            actions={
              globalProvider?.has_api_key ? (
                <Chip size="sm" variant="flat" color="success">已配置 Token</Chip>
              ) : null
            }
          />
          <div className="mt-4">
            {!authStatus.loggedIn ? (
              <p className="text-default-500 m-0">登录后可配置全局 AI 审查设置</p>
            ) : globalProviderLoading ? (
              <p className="text-default-500 m-0">加载中...</p>
            ) : (
              <>
                <div className="flex flex-col gap-3">
                  {providers.length > 0 ? (
                    <Select
                      label="审查引擎"
                      selectedKeys={new Set([selectedProvider])}
                      onSelectionChange={(keys) => {
                        if (keys === 'all') return;
                        const key = Array.from(keys)[0] as string;
                        if (key) setSelectedProvider(key);
                      }}
                      variant="bordered"
                      aria-label="选择审查引擎"
                    >
                      {providers.map((provider) => (
                        <SelectItem key={provider.name}>{provider.label}</SelectItem>
                      ))}
                    </Select>
                  ) : null}
                  <Input
                    label="Base URL"
                    value={globalBaseUrl}
                    onValueChange={setGlobalBaseUrl}
                    placeholder={currentPlaceholders.baseUrl}
                    variant="bordered"
                  />
                  <Input
                    label="Model ID（可选）"
                    value={globalModel}
                    onValueChange={setGlobalModel}
                    placeholder={currentModelPlaceholder}
                    variant="bordered"
                  />
                  <Input
                    label="API Key"
                    type="password"
                    value={globalAuthToken}
                    onValueChange={setGlobalAuthToken}
                    placeholder={
                      globalProvider?.has_api_key
                        ? '已配置（输入新值覆盖）'
                        : currentPlaceholders.apiKey
                    }
                    variant="bordered"
                  />
                </div>
                <div className="mt-4 flex items-center gap-3 flex-wrap">
                  <Button
                    color="primary"
                    onPress={saveGlobalReviewConfig}
                    isDisabled={globalProviderSaving}
                    isLoading={globalProviderSaving}
                  >
                    保存个人设置
                  </Button>
                  <span className="text-default-400 text-xs">
                    作为仓库默认值使用；仓库页可关闭继承并单独覆盖
                  </span>
                </div>
              </>
            )}
          </div>
        </section>

        <section className="py-5 border-t border-divider/60">
          <SectionHeader
            title="全局 Issue 分析配置"
            icon={<Bot size={18} />}
            actions={
              globalIssue?.has_api_key ? (
                <Chip size="sm" variant="flat" color="success">已配置 Token</Chip>
              ) : null
            }
          />
          <div className="mt-4">
            {!authStatus.loggedIn ? (
              <p className="text-default-500 m-0">登录后可配置全局 Issue 分析设置</p>
            ) : globalIssueLoading ? (
              <p className="text-default-500 m-0">加载中...</p>
            ) : (
              <>
                <p className="text-default-500 text-sm mb-4">Issue 分析使用 Forge 引擎，在此配置全局默认 API 凭据和模型</p>
                <div className="flex flex-col gap-3">
                  <Input
                    label="Base URL"
                    value={globalIssueApiUrl}
                    onValueChange={setGlobalIssueApiUrl}
                    placeholder="https://api.anthropic.com"
                    variant="bordered"
                  />
                  <Input
                    label="Model ID"
                    value={globalIssueModel}
                    onValueChange={setGlobalIssueModel}
                    placeholder="claude-sonnet-4-20250514"
                    variant="bordered"
                  />
                  <Input
                    label="API Key"
                    type="password"
                    value={globalIssueApiKey}
                    onValueChange={setGlobalIssueApiKey}
                    placeholder={
                      globalIssue?.has_api_key
                        ? '已配置（输入新值覆盖）'
                        : 'sk-ant-...'
                    }
                    variant="bordered"
                  />
                  <Input
                    label="自定义 Prompt"
                    value={globalIssueCustomPrompt}
                    onValueChange={setGlobalIssueCustomPrompt}
                    placeholder="可选"
                    variant="bordered"
                  />
                </div>
                <div className="mt-4 flex items-center gap-3 flex-wrap">
                  <Button
                    color="primary"
                    onPress={saveGlobalIssueConfig}
                    isDisabled={globalIssueSaving}
                    isLoading={globalIssueSaving}
                  >
                    保存个人设置
                  </Button>
                  <span className="text-default-400 text-xs">
                    仓库可在仓库设置页关闭继承并覆盖这些配置
                  </span>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

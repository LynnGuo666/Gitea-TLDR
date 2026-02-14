import Head from 'next/head';
import { useCallback, useContext, useEffect, useState } from 'react';
import { Button, Chip, Input, Select, SelectItem, addToast } from '@heroui/react';
import { Bot } from 'lucide-react';
import { AuthContext } from '../lib/auth';
import { apiFetch } from '../lib/api';
import PageHeader from '../components/PageHeader';
import SectionHeader from '../components/SectionHeader';
import { GlobalProviderConfig, ProviderInfo } from '../lib/types';

export default function PreferencesPage() {
  const { status: authStatus } = useContext(AuthContext);
  const [globalProvider, setGlobalProvider] = useState<GlobalProviderConfig | null>(null);
  const [globalProviderLoading, setGlobalProviderLoading] = useState(true);
  const [globalProviderSaving, setGlobalProviderSaving] = useState(false);
  const [globalBaseUrl, setGlobalBaseUrl] = useState('');
  const [globalAuthToken, setGlobalAuthToken] = useState('');
  const [globalModel, setGlobalModel] = useState('');
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('claude_code');

  const fetchGlobalProvider = useCallback(async () => {
    if (!authStatus.loggedIn) {
      setGlobalProvider(null);
      setGlobalProviderLoading(false);
      return;
    }

    setGlobalProviderLoading(true);
    try {
      const res = await apiFetch('/api/config/provider-global');
      if (!res.ok) {
        setGlobalProvider(null);
        return;
      }
      const data: GlobalProviderConfig = await res.json();
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
  }, [fetchGlobalProvider]);

  const saveGlobalProviderConfig = async () => {
    if (!authStatus.loggedIn) {
      addToast({ title: '请先登录后再配置', color: 'warning' });
      return;
    }

    setGlobalProviderSaving(true);
    try {
      const res = await apiFetch('/api/config/provider-global', {
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

  const providerPlaceholders: Record<string, { baseUrl: string; apiKey: string }> = {
    claude_code: {
      baseUrl: 'https://api.anthropic.com (留空使用默认)',
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
        <title>个人设置 - Gitea PR Reviewer</title>
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
                    onPress={saveGlobalProviderConfig}
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
      </div>
    </>
  );
}

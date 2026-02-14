import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState, useCallback } from 'react';
import {
  Button,
  Chip,
  Input,
  Select,
  SelectItem,
  Tab,
  Tabs,
  Switch,
  addToast,
} from '@heroui/react';
import {
  FolderGit2,
  RefreshCw,
  ArrowLeft,
  ExternalLink,
  ChevronRight,
} from 'lucide-react';
import PageHeader from '../../../components/PageHeader';
import { Skeleton } from '../../../components/ui';
import { RepoProviderConfig, ProviderInfo } from '../../../lib/types';
import { AuthContext } from '../../../lib/auth';
import { apiFetch } from '../../../lib/api';

const defaultEvents = ['pull_request', 'issue_comment'];
const reviewCatalog = [
  {
    key: 'quality',
    label: '质量保障',
    detail: '架构、风格一致性、重复代码',
  },
  {
    key: 'security',
    label: '安全合规',
    detail: '权限、依赖、输入校验与密钥',
  },
  {
    key: 'performance',
    label: '性能体验',
    detail: '慢查询、循环、资源热点',
  },
  {
    key: 'logic',
    label: '业务逻辑',
    detail: '边界条件、回归风险、异常链路',
  },
];

type WebhookStatus = {
  configured: boolean;
  active: boolean;
  webhook_id: number | null;
  events: string[];
  url: string | null;
  can_setup_webhook?: boolean;
};

type PullRequest = {
  id: number;
  number: number;
  title: string;
  state: string;
  created_at: string;
  updated_at: string;
  user: {
    login: string;
    avatar_url: string;
  };
  head: {
    ref: string;
    repo: {
      name: string;
    } | null;
  };
  base: {
    ref: string;
  };
  html_url: string;
  mergeable: boolean;
  merged: boolean;
  merged_at: string | null;
};

export default function RepoConfigPage() {
  const router = useRouter();
  const { owner, repo } = router.query;
  const [webhookStatus, setWebhookStatus] = useState<WebhookStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [events, setEvents] = useState<string[]>(defaultEvents);
  const [bringBot, setBringBot] = useState(true);
  const [reviewFocus, setReviewFocus] = useState<string[]>([
    'quality',
    'security',
    'performance',
    'logic',
  ]);
  // Claude 配置状态
  const [providerConfig, setProviderConfig] = useState<RepoProviderConfig | null>(null);
  const [providerBaseUrl, setProviderBaseUrl] = useState('');
  const [providerAuthToken, setProviderAuthToken] = useState('');
  const [providerModel, setProviderModel] = useState('');
  const [providerConfigLoading, setProviderConfigLoading] = useState(true);
  const [providerSaving, setProviderSaving] = useState(false);
  const [inheritGlobal, setInheritGlobal] = useState(true);
  const [inheritSaving, setInheritSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('webhook');
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('claude_code');
  // Pull Requests
  const [pulls, setPulls] = useState<PullRequest[]>([]);
  const [pullsLoading, setPullsLoading] = useState(true);
  const [focusLoading, setFocusLoading] = useState(true);
  const [focusSaving, setFocusSaving] = useState(false);

  const { status: authStatus, beginLogin } = useContext(AuthContext);
  const requiresLogin = authStatus.enabled && !authStatus.loggedIn;

  const fetchWebhookStatus = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setStatusLoading(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/webhook-status`);
      if (res.ok) {
        const data = await res.json();
        setWebhookStatus(data);
        // 如果已配置，同步 events
        if (data.configured && data.events?.length) {
          setEvents(data.events);
        }
      } else {
        setWebhookStatus(null);
      }
    } catch {
      setWebhookStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  const fetchProviderConfig = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setProviderConfigLoading(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/provider-config`);
      if (res.ok) {
        const data = await res.json();
        setProviderConfig(data);
        setInheritGlobal(data.inherit_global ?? true);
        const baseUrl = data.api_url;
        if (baseUrl) {
          setProviderBaseUrl(baseUrl);
        } else {
          setProviderBaseUrl('');
        }
        setProviderModel(data.model || '');
        if (data.engine) {
          setSelectedProvider(data.engine);
        }
      } else {
        setProviderConfig(null);
        setInheritGlobal(true);
      }
    } catch {
      setProviderConfig(null);
      setInheritGlobal(true);
    } finally {
      setProviderConfigLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  const fetchPulls = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setPullsLoading(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/pulls?state=all&limit=5`);
      if (res.ok) {
        const data = await res.json();
        setPulls(data.pulls || []);
      } else {
        setPulls([]);
      }
    } catch {
      setPulls([]);
    } finally {
      setPullsLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  const fetchReviewSettings = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;
    setFocusLoading(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/review-settings`);
      if (res.ok) {
        const data = await res.json();
        if (data.default_focus?.length) {
          setReviewFocus(data.default_focus);
        }
      }
    } catch {
      // Keep defaults on error
    } finally {
      setFocusLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  const canEditRepo = webhookStatus?.can_setup_webhook ?? true;

  useEffect(() => {
    if (owner && repo && !requiresLogin) {
      fetchWebhookStatus();
      fetchProviderConfig();
      fetchPulls();
      fetchReviewSettings();
      apiFetch('/api/providers').then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setProviders(data.providers || []);
        }
      }).catch(() => {});
    } else {
      setStatusLoading(false);
      setProviderConfigLoading(false);
      setPullsLoading(false);
      setFocusLoading(false);
    }
  }, [
    owner,
    repo,
    requiresLogin,
    fetchWebhookStatus,
    fetchProviderConfig,
    fetchPulls,
    fetchReviewSettings,
  ]);

  const refreshAll = async () => {
    if (requiresLogin) return;
    setRefreshingAll(true);
    try {
      await Promise.all([
        fetchWebhookStatus(),
        fetchProviderConfig(),
        fetchPulls(),
        fetchReviewSettings(),
      ]);
    } finally {
      setRefreshingAll(false);
    }
  };

  const toggleEvent = (event: string) => {
    setEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  const toggleFocus = async (key: string) => {
    if (focusSaving) return;
    const next = reviewFocus.includes(key)
      ? reviewFocus.filter((item) => item !== key)
      : [...reviewFocus, key];

    // Don't allow empty - must have at least one
    if (next.length === 0) return;

    setReviewFocus(next);
    setFocusSaving(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/review-settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ default_focus: next }),
      });
      if (res.ok) {
        addToast({ title: '审查方向已保存', color: 'success' });
      } else {
        addToast({ title: '保存失败', color: 'danger' });
        setReviewFocus(reviewFocus); // Revert on failure
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
      setReviewFocus(reviewFocus); // Revert on failure
    } finally {
      setFocusSaving(false);
    }
  };

  const enableWebhook = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setToggling(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events, bring_bot: bringBot }),
      });
      const data = await res.json();
      if (res.ok) {
        addToast({ title: 'Webhook 已启用', color: 'success' });
        await fetchWebhookStatus();
      } else {
        addToast({ title: data.detail || 'Webhook 配置失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setToggling(false);
    }
  };

  const disableWebhook = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setToggling(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/webhook`, {
        method: 'DELETE',
      });
      if (res.ok) {
        addToast({ title: 'Webhook 已禁用', color: 'success' });
        setWebhookStatus({
          configured: false,
          active: false,
          webhook_id: null,
          events: [],
          url: null,
        });
      } else {
        const data = await res.json();
        addToast({ title: data.detail || '删除 Webhook 失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setToggling(false);
    }
  };

  const handleToggle = () => {
    if (webhookStatus?.configured) {
      disableWebhook();
    } else {
      enableWebhook();
    }
  };

  const saveProviderConfig = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo || inheritGlobal) return;

    setProviderSaving(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/provider-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine: selectedProvider,
          model: providerModel || null,
          api_url: providerBaseUrl || null,
          api_key: providerAuthToken || null,
          inherit_global: false,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        addToast({ title: 'AI 审查配置已保存', color: 'success' });
        setInheritGlobal(false);
        setProviderConfig((prev) => ({
          configured: true,
          api_url: data.api_url,
          engine: data.engine,
          model: data.model,
          has_api_key: data.has_api_key,
          inherit_global: false,
          has_global_config: prev?.has_global_config ?? false,
          global_api_url: prev?.global_api_url ?? null,
          global_has_api_key: prev?.global_has_api_key ?? false,
          global_engine: prev?.global_engine ?? null,
          global_model: prev?.global_model ?? null,
        }));
        setProviderAuthToken('');
      } else {
        addToast({ title: data.detail || '保存失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setProviderSaving(false);
    }
  };

  const toggleInheritGlobal = async (nextValue: boolean) => {
    if (requiresLogin || !owner || !repo || !canEditRepo || inheritSaving) return;

    setInheritSaving(true);
    try {
      const res = await apiFetch(`/api/repos/${owner}/${repo}/provider-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inherit_global: nextValue }),
      });
      const data = await res.json();

      if (res.ok) {
        setInheritGlobal(nextValue);
        addToast({
          title: nextValue ? '已切换为全局设置' : '已切换为仓库独立设置',
          color: 'success',
        });
        if (nextValue) {
          setProviderBaseUrl(data.api_url || '');
          setProviderModel(data.model || '');
          setProviderAuthToken('');
        }
        await fetchProviderConfig();
      } else {
        addToast({ title: data.detail || '切换失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setInheritSaving(false);
    }
  };

  if (!owner || !repo) {
    return null;
  }

  const isWebhookEnabled = webhookStatus?.configured && webhookStatus?.active;

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
  const providerLabel = (name: string) => providers.find((p) => p.name === name)?.label || name;

  return (
    <>
      <Head>
        <title>{`${owner}/${repo} - 配置`}</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <section className="pb-4">
          <PageHeader
            title={`${owner}/${repo}`}
            icon={<FolderGit2 size={20} />}
            actions={
              <>
                <Button isIconOnly variant="bordered" size="sm" onPress={refreshAll} isDisabled={refreshingAll} aria-label="刷新仓库数据">
                  <RefreshCw size={16} className={refreshingAll ? 'animate-spin' : ''} />
                </Button>
                <Button variant="light" size="sm" onPress={() => router.push('/')}>
                  <ArrowLeft size={16} /> 返回
                </Button>
              </>
            }
          />
        </section>

        <section className="pt-2 border-t border-divider/60">
          <Tabs
            selectedKey={activeTab}
            onSelectionChange={(key) => setActiveTab(String(key))}
            variant="underlined"
            color="primary"
          >
            <Tab key="webhook" title="自动审查" />
            <Tab key="focus" title="审查方向" />
            <Tab key="claude" title="AI 审查配置" />
            <Tab key="pulls" title="最新 PR" />
          </Tabs>
        </section>

        {activeTab === 'webhook' && (
          <section className="py-5">
            <div>
              {requiresLogin ? (
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="m-0 text-base">需要登录</h3>
                    <p className="m-0 text-default-500 text-sm mt-1">连接 Gitea 后才能查看和配置 Webhook</p>
                  </div>
                  <Button color="primary" onPress={beginLogin}>登录</Button>
                </div>
              ) : statusLoading ? (
                <div className="flex items-center justify-between gap-4">
                  <Skeleton width={200} height={20} />
                  <Skeleton width={52} height={28} />
                </div>
              ) : (
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <h3 className="m-0 text-base flex items-center gap-2">
                      <span className={`w-2.5 h-2.5 rounded-full ${isWebhookEnabled ? 'bg-success' : 'bg-default-300'}`} />
                      {isWebhookEnabled ? 'Webhook 已启用' : 'Webhook 未启用'}
                    </h3>
                    <p className="m-0 text-default-500 text-sm mt-1">
                      {canEditRepo
                        ? isWebhookEnabled
                          ? `监听事件: ${webhookStatus?.events?.join(', ') || '无'}`
                          : '启用后，PR 将自动触发代码审查'
                        : '组织仓库需要组织管理员权限才能修改配置'}
                    </p>
                  </div>
                  <Switch
                    isSelected={!!isWebhookEnabled}
                    isDisabled={toggling || !canEditRepo}
                    onValueChange={() => {
                      if (!toggling) handleToggle();
                    }}
                    aria-label="切换 Webhook"
                  />
                </div>
              )}

              {!requiresLogin && !statusLoading && !isWebhookEnabled && canEditRepo && (
                <div className="mt-4 border-t border-divider pt-4">
                  <p className="text-default-500 text-sm m-0 mb-2">启用前可选择监听的事件：</p>
                  <div className="flex flex-wrap items-center gap-2">
                    {defaultEvents.map((event) => (
                      <Chip
                        key={event}
                        variant={events.includes(event) ? 'solid' : 'bordered'}
                        color={events.includes(event) ? 'primary' : 'default'}
                        className="cursor-pointer"
                        onClick={() => toggleEvent(event)}
                      >
                        {event}
                      </Chip>
                    ))}
                    <label className="flex items-center gap-2 text-sm cursor-pointer ml-2">
                      <input
                        type="checkbox"
                        checked={bringBot}
                        onChange={(e) => setBringBot(e.target.checked)}
                        className="accent-primary"
                      />
                      <span>邀请 bot 协作</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {activeTab === 'focus' && (
          <section className="py-5">
            {focusLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Skeleton width="100%" height={80} className="rounded-xl" />
                <Skeleton width="100%" height={80} className="rounded-xl" />
                <Skeleton width="100%" height={80} className="rounded-xl" />
                <Skeleton width="100%" height={80} className="rounded-xl" />
              </div>
            ) : (
              <>
                <div className="mb-4 flex justify-end">
                  <Chip size="sm" variant="flat">
                    {reviewFocus.length} 个已启用
                  </Chip>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {reviewCatalog.map((item) => {
                    const active = reviewFocus.includes(item.key);
                    return (
                      <button
                        key={item.key}
                        disabled={focusSaving}
                        className={`text-left p-4 rounded-xl transition-all cursor-pointer ${
                          active
                            ? 'bg-primary-50 ring-1 ring-primary'
                            : 'bg-default-100 hover:bg-default-200'
                        } ${focusSaving ? 'opacity-70 cursor-not-allowed' : ''}`}
                        onClick={() => toggleFocus(item.key)}
                      >
                        <strong className="text-sm text-foreground">{item.label}</strong>
                        <p className="m-0 text-xs text-default-500 mt-1">{item.detail}</p>
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </section>
        )}

        {activeTab === 'claude' && (
          <section className="py-5">
            {providerConfig?.has_api_key ? (
              <div className="mb-4 flex justify-end">
                <Chip size="sm" variant="flat" color="success">已配置 Token</Chip>
              </div>
            ) : null}

            <div>
              {requiresLogin ? (
                <p className="text-default-500 m-0">登录后可配置 AI 审查 API</p>
              ) : providerConfigLoading ? (
                <div className="flex flex-col gap-3">
                  <Skeleton width="100%" height={40} />
                  <Skeleton width="100%" height={40} />
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-4 rounded-xl bg-default-100 px-4 py-3 mb-4">
                    <div>
                      <p className="m-0 text-sm font-medium">与全局设置保持一致</p>
                      <p className="m-0 mt-1 text-xs text-default-500">
                        {inheritGlobal
                          ? '当前使用全局 AI 审查配置'
                          : '当前使用此仓库的独立 AI 审查配置'}
                      </p>
                    </div>
                    <Switch
                      isSelected={inheritGlobal}
                      isDisabled={!canEditRepo || inheritSaving}
                      onValueChange={toggleInheritGlobal}
                      aria-label="与全局设置保持一致"
                    />
                  </div>

                  {inheritGlobal ? (
                    <div className="rounded-xl bg-default-100 px-4 py-3">
                      {providerConfig?.has_global_config ? (
                        <>
                          <p className="m-0 text-sm text-default-700">
                            审查引擎: {providerLabel(providerConfig.global_engine || 'claude_code')}
                          </p>
                          <p className="m-0 mt-1 text-sm text-default-700">
                            模型 ID: {providerConfig.global_model || '未设置'}
                          </p>
                          <p className="m-0 mt-1 text-sm text-default-700">
                            Base URL: {providerConfig.global_api_url || '默认官方地址'}
                          </p>
                          <p className="m-0 mt-1 text-sm text-default-700">
                            API Key: {providerConfig.global_has_api_key ? '已配置' : '未配置'}
                          </p>
                        </>
                      ) : (
                        <p className="m-0 text-sm text-warning-600">
                          尚未配置全局 AI 审查设置，请先在「个人设置」中配置
                        </p>
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-col gap-3">
                        {providers.length > 0 && (
                          <Select
                            label="审查引擎"
                            selectedKeys={new Set([selectedProvider])}
                            onSelectionChange={(keys) => {
                              if (keys === 'all') return;
                              const key = Array.from(keys)[0] as string;
                              if (key) setSelectedProvider(key);
                            }}
                            isDisabled={!canEditRepo}
                            variant="bordered"
                            aria-label="选择审查引擎"
                          >
                            {providers.map((p) => (
                              <SelectItem key={p.name}>{p.label}</SelectItem>
                            ))}
                          </Select>
                        )}
                        <Input
                          label="Base URL"
                          value={providerBaseUrl}
                          onValueChange={setProviderBaseUrl}
                          placeholder={currentPlaceholders.baseUrl}
                          isDisabled={!canEditRepo}
                          variant="bordered"
                        />
                        <Input
                          label="Model ID（可选）"
                          value={providerModel}
                          onValueChange={setProviderModel}
                          placeholder={currentModelPlaceholder}
                          isDisabled={!canEditRepo}
                          variant="bordered"
                        />
                        <Input
                          label="API Key"
                          type="password"
                          value={providerAuthToken}
                          onValueChange={setProviderAuthToken}
                          placeholder={providerConfig?.has_api_key ? '已配置（输入新值覆盖）' : currentPlaceholders.apiKey}
                          isDisabled={!canEditRepo}
                          variant="bordered"
                        />
                      </div>
                      <div className="mt-4 flex items-center gap-3 flex-wrap">
                        <Button
                          color="primary"
                          onPress={saveProviderConfig}
                          isDisabled={providerSaving || !canEditRepo}
                          isLoading={providerSaving}
                        >
                          保存配置
                        </Button>
                        <span className="text-default-400 text-xs">
                          {canEditRepo
                            ? '配置后，审查 PR 时将使用此仓库的 API Key'
                            : '组织仓库需要组织管理员权限才能修改 AI 审查配置'}
                        </span>
                      </div>
                    </>
                  )}
                  <div className="mt-3 text-default-400 text-xs">
                    全局配置在“个人设置”维护，仓库仅在需要时单独覆盖
                  </div>
                </>
              )}
            </div>
          </section>
        )}

        {activeTab === 'pulls' && (
          <section className="py-5">
            <div>
              {requiresLogin ? (
                <p className="text-default-500 m-0">登录后可查看 Pull Request</p>
              ) : pullsLoading ? (
                <div className="flex flex-col gap-3">
                  <Skeleton width="100%" height={80} />
                  <Skeleton width="100%" height={80} />
                  <Skeleton width="100%" height={80} />
                </div>
              ) : pulls.length === 0 ? (
                <p className="text-default-500 m-0">暂无 Pull Request</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {pulls.map((pr) => {
                    const prDate = new Date(pr.updated_at);
                    const now = new Date();
                    const diffMs = now.getTime() - prDate.getTime();
                    const diffMins = Math.floor(diffMs / 60000);
                    const diffHours = Math.floor(diffMs / 3600000);
                    const diffDays = Math.floor(diffMs / 86400000);

                    let timeAgo = '';
                    if (diffDays > 0) {
                      timeAgo = `${diffDays} 天前`;
                    } else if (diffHours > 0) {
                      timeAgo = `${diffHours} 小时前`;
                    } else if (diffMins > 0) {
                      timeAgo = `${diffMins} 分钟前`;
                    } else {
                      timeAgo = '刚刚';
                    }

                    let statusColor: 'success' | 'danger' | 'primary' = 'primary';
                    let statusText = '打开';
                    if (pr.merged) {
                      statusColor = 'success';
                      statusText = '已合并';
                    } else if (pr.state === 'closed') {
                      statusColor = 'danger';
                      statusText = '已关闭';
                    }

                    return (
                      <a
                        key={pr.id}
                        href={pr.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex items-center gap-3 p-3 rounded-xl bg-default-100 no-underline text-foreground transition-all hover:bg-default-200"
                      >
                        <img
                          src={pr.user.avatar_url}
                          alt={pr.user.login}
                          className="w-9 h-9 rounded-full shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{pr.title}</div>
                          <div className="text-xs text-default-400 mt-0.5 flex items-center gap-1.5 flex-wrap">
                            <span>#{pr.number}</span>
                            <span>·</span>
                            <span>{pr.user.login}</span>
                            <span>·</span>
                            <span>{timeAgo}</span>
                          </div>
                          <div className="text-xs text-default-400 mt-1 flex items-center gap-1">
                            <code className="bg-default-100 px-1.5 py-0.5 rounded text-[11px] max-w-[120px] truncate">{pr.head.ref}</code>
                            <ChevronRight size={12} />
                            <code className="bg-default-100 px-1.5 py-0.5 rounded text-[11px] max-w-[120px] truncate">{pr.base.ref}</code>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Chip size="sm" variant="flat" color={statusColor}>{statusText}</Chip>
                          <ExternalLink size={16} className="text-default-400 group-hover:text-primary transition-colors" />
                        </div>
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </>
  );
}

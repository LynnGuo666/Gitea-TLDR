import Head from 'next/head';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { Button, Card, CardBody, Chip, Input, Select, SelectItem, Switch, Tab, Tabs, Textarea } from '@heroui/react';
import PageHeader from '../../../components/PageHeader';
import SectionHeader from '../../../components/SectionHeader';
import { apiFetch } from '../../../lib/api';
import { relativeTime, readErrorMessage } from '../../../lib/utils';
import { ProviderCredential, RepositoryConfiguration, WebhookStatus, PullRequest } from '../../../lib/types';

type Scenario = 'review' | 'issue';

const FOCUS_CATALOG = [
  { key: 'quality', label: '质量保障', detail: '架构、风格一致性、重复代码' },
  { key: 'security', label: '安全合规', detail: '权限、依赖、输入校验与密钥' },
  { key: 'performance', label: '性能体验', detail: '慢查询、循环、资源热点' },
  { key: 'logic', label: '业务逻辑', detail: '边界条件、回归风险、异常链路' },
];

const SCENARIO_OPTIONS: { key: Scenario; label: string; detail: string }[] = [
  { key: 'review', label: 'PR 审查', detail: '分析代码变更，生成内联评论与概览' },
  { key: 'issue', label: 'Issue 分析', detail: '定位 Issue 根因，提供解决方案' },
];

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
  const [activeTab, setActiveTab] = useState('webhook');
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

  const [webhookStatus, setWebhookStatus] = useState<WebhookStatus | null>(null);
  const [webhookLoading, setWebhookLoading] = useState(true);
  const [webhookConfiguring, setWebhookConfiguring] = useState(false);
  const [webhookError, setWebhookError] = useState('');
  const [webhookSuccess, setWebhookSuccess] = useState('');
  const [events, setEvents] = useState<string[]>(['pull_request', 'issue_comment']);

  const [pulls, setPulls] = useState<PullRequest[]>([]);
  const [pullsLoading, setPullsLoading] = useState(true);

  const isReadOnly = hasAdmin === false;

  const featureList = form.features.split(',').map((s) => s.trim()).filter(Boolean);
  const featuresHasComment = featureList.includes('comment');
  const featuresOther = featureList.filter((f) => f !== 'comment');

  const loadStatic = async () => {
    try {
      const res = await apiFetch('/api/v2/provider-credentials');
      if (res.ok) setCredentials((await res.json()).credentials || []);
    } catch {
      // non-critical
    }
  };

  const loadPermissions = async () => {
    if (!owner || !repo) return;
    setPermissionsLoading(true);
    try {
      const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/permissions`);
      if (res.ok) {
        const perms = (await res.json()) as { admin?: boolean };
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
    try {
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
    } catch {
      // handled silently
    }
  };

  const loadWebhook = async () => {
    if (!owner || !repo) return;
    setWebhookLoading(true);
    try {
      const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/webhook-status`);
      if (res.ok) {
        const data = (await res.json()) as WebhookStatus;
        setWebhookStatus(data);
        const hookEvents = data.hooks?.[0]?.events;
        if (hookEvents?.length) setEvents(hookEvents);
      } else {
        setWebhookError(await readErrorMessage(res, '无法获取 Webhook 状态'));
      }
    } catch {
      setWebhookError('无法获取 Webhook 状态，请稍后重试');
    } finally {
      setWebhookLoading(false);
    }
  };

  const loadPulls = async () => {
    if (!owner || !repo) return;
    setPullsLoading(true);
    try {
      const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/pulls?state=all&limit=5`);
      if (res.ok) {
        const data = (await res.json()) as { pulls: PullRequest[] };
        setPulls(data.pulls || []);
      }
    } catch {
      // handled silently
    } finally {
      setPullsLoading(false);
    }
  };

  useEffect(() => {
    if (!router.isReady) return;
    void loadStatic();
    void loadPermissions();
    void loadWebhook();
    void loadPulls();
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
        engine: form.engine || config?.engine || 'forge',
        model: form.model || null,
        credential_id: form.credential_id ? Number(form.credential_id) : null,
        wire_api: form.wire_api || config?.wire_api || null,
        temperature: form.temperature ? Number(form.temperature) : null,
        max_tokens: form.max_tokens ? Number(form.max_tokens) : null,
        custom_prompt: form.custom_prompt || null,
        focus: form.focus.split(',').map((s) => s.trim()).filter(Boolean),
        features: form.features.split(',').map((s) => s.trim()).filter(Boolean),
        is_active: form.is_active,
      }),
    });
    if (res.ok) await loadConfig();
  };

  const configureWebhook = async () => {
    if (webhookConfiguring) return;
    setWebhookConfiguring(true);
    setWebhookError('');
    setWebhookSuccess('');
    try {
      const res = await apiFetch(`/api/v2/repos/${owner}/${repo}/webhook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events }),
      });
      if (!res.ok) {
        setWebhookError(await readErrorMessage(res, 'Webhook 保存失败'));
        return;
      }
      await loadWebhook();
      setWebhookSuccess('Webhook 已保存');
    } catch {
      setWebhookError('Webhook 保存失败，请检查网络或稍后重试');
    } finally {
      setWebhookConfiguring(false);
    }
  };

  const activeHook = webhookStatus?.hooks?.[0];
  const focusKeys = form.focus.split(',').map((s) => s.trim()).filter(Boolean);

  const toggleFocus = (key: string) => {
    const current = new Set(focusKeys);
    if (current.has(key)) current.delete(key);
    else current.add(key);
    setForm({ ...form, focus: Array.from(current).join(',') });
  };

  return (
    <>
      <Head>
        <title>{owner}/{repo} - 仓库配置 - Gitea TLDR</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-6">
        <PageHeader title={`${owner}/${repo}`} subtitle="仓库独立配置，运行时不会从全局 fallback" />

        {isReadOnly && (
          <div className="rounded-md border border-default-300 bg-default-100 p-4 text-sm text-default-600 flex items-center gap-3">
            <Chip size="sm" variant="flat" color="default">只读</Chip>
            你没有此仓库的管理权限，配置为只读查看。如需修改请联系仓库管理员。
          </div>
        )}

        <Tabs
          selectedKey={activeTab}
          onSelectionChange={(k) => setActiveTab(String(k))}
          variant="underlined"
          color="primary"
        >
          <Tab key="webhook" title="自动审查" />
          <Tab key="focus" title="审查方向" />
          <Tab key="config" title="场景配置" />
          <Tab key="pulls" title="最新 PR" />
        </Tabs>

        {activeTab === 'webhook' && (
          <section className="flex flex-col gap-6">
            <SectionHeader title="自动审查" />
            {webhookLoading ? (
              <div className="text-sm text-default-400">加载中…</div>
            ) : (
              <div className="flex flex-col gap-5">
                <div className="flex items-center justify-between rounded-lg border border-divider p-4">
                  <div>
                    <p className="font-medium text-sm">Webhook 状态</p>
                    <p className="text-xs text-default-500 mt-1">
                      {webhookStatus?.configured
                        ? `已配置${activeHook ? (activeHook.active ? '，运行中' : '，已停用') : ''}`
                        : '未配置'}
                    </p>
                    {activeHook?.config?.url && (
                      <p className="text-xs text-default-400 mt-0.5 truncate max-w-xs">{activeHook.config.url}</p>
                    )}
                  </div>
                  <Switch
                    isSelected={activeHook?.active ?? false}
                    isDisabled
                    aria-label="Webhook 启用状态（只读）"
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <p className="text-sm font-medium">触发事件</p>
                  <div className="flex gap-4">
                    {(['pull_request', 'issue_comment'] as const).map((ev) => (
                      <label key={ev} className="flex items-center gap-2 cursor-pointer select-none text-sm">
                        <input
                          type="checkbox"
                          checked={events.includes(ev)}
                          disabled={isReadOnly}
                          onChange={() =>
                            setEvents((prev) =>
                              prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]
                            )
                          }
                          className="rounded"
                        />
                        {ev}
                      </label>
                    ))}
                  </div>
                </div>

                {webhookError && (
                  <div className="rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
                    {webhookError}
                  </div>
                )}

                {webhookSuccess && (
                  <div className="rounded-md border border-success/40 bg-success/10 p-3 text-sm text-success">
                    {webhookSuccess}
                  </div>
                )}

                <Button
                  color="primary"
                  onPress={configureWebhook}
                  isLoading={webhookConfiguring}
                  isDisabled={isReadOnly}
                >
                  {webhookStatus?.configured ? '重新配置 Webhook' : '启用 Webhook'}
                </Button>
              </div>
            )}
          </section>
        )}

        {activeTab === 'focus' && (
          <section className="flex flex-col gap-6">
            <SectionHeader title="审查方向" />
            <div className="grid grid-cols-2 gap-4">
              {FOCUS_CATALOG.map(({ key, label, detail }) => {
                const selected = focusKeys.includes(key);
                return (
                  <Card
                    key={key}
                    isPressable={!isReadOnly}
                    onPress={() => !isReadOnly && toggleFocus(key)}
                    className={`border-2 transition-colors ${
                      selected ? 'border-primary bg-primary/5' : 'border-divider'
                    }`}
                  >
                    <CardBody className="flex flex-col gap-1 p-4">
                      <span className="font-semibold text-sm">{label}</span>
                      <span className="text-xs text-default-500">{detail}</span>
                    </CardBody>
                  </Card>
                );
              })}
            </div>
            <Button color="primary" onPress={saveConfig} isDisabled={isReadOnly}>
              保存审查方向
            </Button>
          </section>
        )}

        {activeTab === 'config' && (
          <section className="flex flex-col gap-6">
            <SectionHeader title="场景配置" />

            <div>
              <p className="text-sm font-medium mb-3">场景选择</p>
              <div className="grid grid-cols-2 gap-3">
                {SCENARIO_OPTIONS.map(({ key, label, detail }) => (
                  <Card
                    key={key}
                    isPressable
                    onPress={() => setScenario(key)}
                    className={`border-2 transition-colors ${
                      scenario === key ? 'border-primary bg-primary/5' : 'border-divider'
                    }`}
                  >
                    <CardBody className="p-4 flex flex-col gap-1">
                      <span className="font-semibold text-sm">
                        {scenario === key && '✓ '}{label}
                      </span>
                      <span className="text-xs text-default-500">{detail}</span>
                    </CardBody>
                  </Card>
                ))}
              </div>
            </div>

            {permissionsLoading ? (
              <div className="text-sm text-default-400">加载权限…</div>
            ) : configurationRequired ? (
              <div className="rounded-md border border-warning/50 bg-warning/10 p-4 text-sm text-warning">
                此仓库尚未为「{SCENARIO_OPTIONS.find((s) => s.key === scenario)?.label}」场景初始化配置，请联系管理员完成初始化后再访问此页面。
              </div>
            ) : config ? (
              <div className="flex flex-col gap-5">
                <div className="flex items-center justify-between rounded-lg border border-divider p-4">
                  <div>
                    <p className="font-medium text-sm">启用此场景配置</p>
                    <p className="text-xs text-default-500 mt-1">关闭后此场景不会自动触发</p>
                  </div>
                  <Switch
                    isSelected={form.is_active}
                    isDisabled={isReadOnly}
                    onValueChange={(is_active) => setForm({ ...form, is_active })}
                    aria-label="启用此场景配置"
                  />
                </div>

                <div className="h-px bg-divider" />

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="flex flex-col gap-1.5">
                    <span className="text-tiny text-default-500">审查引擎</span>
                    <div className="flex h-10 items-center">
                      <Chip color="primary" variant="flat">Forge</Chip>
                    </div>
                  </div>
                  <Input
                    label="模型"
                    placeholder="例：claude-opus-4-5"
                    value={form.model}
                    isDisabled={isReadOnly}
                    onValueChange={(model) => setForm({ ...form, model })}
                  />
                  <Select
                    label="API 凭证"
                    isDisabled={isReadOnly}
                    selectedKeys={form.credential_id ? new Set([form.credential_id]) : new Set([])}
                    onSelectionChange={(keys) => setForm({ ...form, credential_id: String(Array.from(keys)[0] || '') })}
                  >
                    {credentials.map((c) => <SelectItem key={String(c.id)}>{c.name}</SelectItem>)}
                  </Select>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <Input
                    label="Temperature"
                    placeholder="0.0 – 1.0，留空使用默认值"
                    value={form.temperature}
                    isDisabled={isReadOnly}
                    onValueChange={(temperature) => setForm({ ...form, temperature })}
                  />
                  <Input
                    label="最大 Token 数"
                    placeholder="留空使用默认值"
                    value={form.max_tokens}
                    isDisabled={isReadOnly}
                    onValueChange={(max_tokens) => setForm({ ...form, max_tokens })}
                  />
                </div>

                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between rounded-lg border border-divider p-4">
                    <div>
                      <p className="font-medium text-sm">启用行内评论</p>
                      <p className="text-xs text-default-500 mt-1">将审查意见作为 inline comment 直接标注到代码行</p>
                    </div>
                    <Switch
                      isSelected={featuresHasComment}
                      isDisabled={isReadOnly}
                      onValueChange={(checked) => {
                        const next = checked ? [...featuresOther, 'comment'] : featuresOther;
                        setForm({ ...form, features: next.join(',') });
                      }}
                      aria-label="启用行内评论"
                    />
                  </div>
                  {featuresOther.length > 0 && (
                    <div className="flex gap-2 flex-wrap px-1">
                      {featuresOther.map((f) => (
                        <Chip key={f} size="sm" variant="flat">{f}</Chip>
                      ))}
                    </div>
                  )}
                </div>

                <Textarea
                  label="自定义提示词补充"
                  placeholder="可在此追加额外的审查要求或上下文，将追加到默认提示词之后"
                  value={form.custom_prompt}
                  isDisabled={isReadOnly}
                  onValueChange={(custom_prompt) => setForm({ ...form, custom_prompt })}
                />

                <div className="rounded-md border border-default-200 bg-default-100 p-3 text-sm text-default-500">
                  ℹ 审查方向（focus）请在&ldquo;审查方向&rdquo; Tab 中配置。
                </div>

                <Button color="primary" onPress={saveConfig} isDisabled={isReadOnly}>保存仓库配置</Button>
              </div>
            ) : null}
          </section>
        )}

        {activeTab === 'pulls' && (
          <section className="flex flex-col gap-4">
            <SectionHeader title="最新 PR" />
            {pullsLoading ? (
              <div className="text-sm text-default-400">加载中…</div>
            ) : pulls.length === 0 ? (
              <div className="text-sm text-default-400">暂无 PR 记录。</div>
            ) : (
              <div className="flex flex-col gap-3">
                {pulls.map((pr) => {
                  const chipColor = pr.merged ? 'success' : pr.state === 'closed' ? 'danger' : 'primary';
                  const chipLabel = pr.merged ? '已合并' : pr.state === 'closed' ? '已关闭' : '开放';
                  return (
                    <div key={pr.id} className="flex items-start gap-4 rounded-lg border border-divider p-4">
                      <Image
                        src={pr.user.avatar_url}
                        alt={pr.user.login}
                        width={32}
                        height={32}
                        className="w-8 h-8 rounded-full shrink-0 mt-0.5"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <a
                            href={pr.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-medium text-sm hover:underline"
                          >
                            {pr.title}
                          </a>
                          <span className="text-xs text-default-400">#{pr.number}</span>
                          <Chip size="sm" color={chipColor} variant="flat">{chipLabel}</Chip>
                        </div>
                        <div className="flex items-center gap-2 mt-1 text-xs text-default-500 flex-wrap">
                          <span>{pr.user.login}</span>
                          <span>·</span>
                          <span>{pr.head.ref} → {pr.base.ref}</span>
                          <span>·</span>
                          <span>{relativeTime(pr.created_at)}</span>
                          <a
                            href={pr.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-auto text-default-400 hover:text-primary"
                          >
                            ↗
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </div>
    </>
  );
}

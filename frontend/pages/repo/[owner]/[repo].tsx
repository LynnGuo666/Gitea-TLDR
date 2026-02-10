import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState, useCallback } from 'react';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  Input,
  Switch,
  addToast,
} from '@heroui/react';
import {
  FolderGit2,
  Bot,
  Settings,
  RefreshCw,
  GitPullRequest,
  ArrowLeft,
  ExternalLink,
  ChevronRight,
} from 'lucide-react';
import { Skeleton } from '../../../components/ui';
import { PublicConfig, RepoClaudeConfig } from '../../../lib/types';
import { AuthContext } from '../../../lib/auth';

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
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [webhookStatus, setWebhookStatus] = useState<WebhookStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [events, setEvents] = useState<string[]>(defaultEvents);
  const [bringBot, setBringBot] = useState(true);
  const [reviewFocus, setReviewFocus] = useState<string[]>([
    'quality',
    'security',
    'performance',
  ]);
  // Claude 配置状态
  const [claudeConfig, setClaudeConfig] = useState<RepoClaudeConfig | null>(null);
  const [claudeBaseUrl, setClaudeBaseUrl] = useState('');
  const [claudeAuthToken, setClaudeAuthToken] = useState('');
  const [claudeConfigLoading, setClaudeConfigLoading] = useState(true);
  const [claudeSaving, setClaudeSaving] = useState(false);
  // Pull Requests
  const [pulls, setPulls] = useState<PullRequest[]>([]);
  const [pullsLoading, setPullsLoading] = useState(true);

  const { status: authStatus, beginLogin } = useContext(AuthContext);
  const requiresLogin = authStatus.enabled && !authStatus.loggedIn;

  const fetchWebhookStatus = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setStatusLoading(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/webhook-status`);
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

  const fetchClaudeConfig = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setClaudeConfigLoading(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/claude-config`);
      if (res.ok) {
        const data = await res.json();
        setClaudeConfig(data);
        if (data.anthropic_base_url) {
          setClaudeBaseUrl(data.anthropic_base_url);
        }
      } else {
        setClaudeConfig(null);
      }
    } catch {
      setClaudeConfig(null);
    } finally {
      setClaudeConfigLoading(false);
    }
  }, [owner, repo, requiresLogin]);

  const fetchPulls = useCallback(async () => {
    if (!owner || !repo || requiresLogin) return;

    setPullsLoading(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/pulls?state=all&limit=5`);
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

  useEffect(() => {
    fetch('/api/config/public')
      .then((res) => res.json())
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  const canEditRepo = webhookStatus?.can_setup_webhook ?? true;

  useEffect(() => {
    if (owner && repo && !requiresLogin) {
      fetchWebhookStatus();
      fetchClaudeConfig();
      fetchPulls();
    } else {
      setStatusLoading(false);
      setClaudeConfigLoading(false);
      setPullsLoading(false);
    }
  }, [owner, repo, requiresLogin, fetchWebhookStatus, fetchClaudeConfig, fetchPulls]);

  const toggleEvent = (event: string) => {
    setEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  const toggleFocus = (key: string) => {
    setReviewFocus((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    );
  };

  const enableWebhook = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setToggling(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/setup`, {
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
      const res = await fetch(`/api/repos/${owner}/${repo}/webhook`, {
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

  const saveClaudeConfig = async () => {
    if (requiresLogin || !owner || !repo || !canEditRepo) return;

    setClaudeSaving(true);
    try {
      const res = await fetch(`/api/repos/${owner}/${repo}/claude-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          anthropic_base_url: claudeBaseUrl || null,
          anthropic_auth_token: claudeAuthToken || null,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        addToast({ title: 'Claude 配置已保存', color: 'success' });
        setClaudeConfig({
          configured: true,
          anthropic_base_url: data.anthropic_base_url,
          has_auth_token: data.has_auth_token,
        });
        setClaudeAuthToken('');
      } else {
        addToast({ title: data.detail || '保存失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setClaudeSaving(false);
    }
  };

  if (!owner || !repo) {
    return null;
  }

  const isWebhookEnabled = webhookStatus?.configured && webhookStatus?.active;

  return (
    <>
      <Head>
        <title>{`${owner}/${repo} - 配置`}</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <Card>
          <CardBody>
            <div className="flex items-center gap-4">
              <Button variant="light" size="sm" onPress={() => router.push('/')}>
                <ArrowLeft size={16} /> 返回
              </Button>
              <div className="flex items-center gap-2.5">
                <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center">
                  <FolderGit2 size={20} />
                </span>
                <h1 className="m-0 text-lg font-semibold">{`${owner}/${repo}`}</h1>
              </div>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center">
                <Settings size={18} />
              </span>
              <h2 className="m-0 text-lg font-semibold">自动审查</h2>
            </div>
            {!requiresLogin && !statusLoading && (
              <Button isIconOnly variant="bordered" size="sm" onPress={fetchWebhookStatus} aria-label="刷新状态">
                <RefreshCw size={16} />
              </Button>
            )}
          </CardHeader>
          <CardBody>
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
                  onValueChange={() => { if (!toggling) handleToggle(); }}
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
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center">
                <Bot size={18} />
              </span>
              <h2 className="m-0 text-lg font-semibold">审查方向</h2>
            </div>
            <Chip size="sm" variant="flat">{reviewFocus.length} 个已启用</Chip>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {reviewCatalog.map((item) => {
                const active = reviewFocus.includes(item.key);
                return (
                  <button
                    key={item.key}
                    className={`text-left p-4 rounded-xl border transition-all cursor-pointer bg-transparent ${
                      active
                        ? 'border-primary bg-primary-50'
                        : 'border-divider hover:border-default-300 hover:bg-default-50'
                    }`}
                    onClick={() => toggleFocus(item.key)}
                  >
                    <strong className="text-sm text-foreground">{item.label}</strong>
                    <p className="m-0 text-xs text-default-500 mt-1">{item.detail}</p>
                  </button>
                );
              })}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center">
                <Settings size={18} />
              </span>
              <h2 className="m-0 text-lg font-semibold">Claude 配置</h2>
            </div>
            {claudeConfig?.has_auth_token && (
              <Chip size="sm" variant="flat" color="success">已配置 Token</Chip>
            )}
          </CardHeader>
          <CardBody>
            {requiresLogin ? (
              <p className="text-default-500 m-0">登录后可配置 Claude API</p>
            ) : claudeConfigLoading ? (
              <div className="flex flex-col gap-3">
                <Skeleton width="100%" height={40} />
                <Skeleton width="100%" height={40} />
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-3">
                  <Input
                    label="Base URL"
                    value={claudeBaseUrl}
                    onValueChange={setClaudeBaseUrl}
                    placeholder="https://api.anthropic.com (留空使用默认)"
                    isDisabled={!canEditRepo}
                    variant="bordered"
                  />
                  <Input
                    label="API Key"
                    type="password"
                    value={claudeAuthToken}
                    onValueChange={setClaudeAuthToken}
                    placeholder={claudeConfig?.has_auth_token ? '已配置（输入新值覆盖）' : 'sk-ant-...'}
                    isDisabled={!canEditRepo}
                    variant="bordered"
                  />
                </div>
                <div className="mt-4 flex items-center gap-3 flex-wrap">
                  <Button
                    color="primary"
                    onPress={saveClaudeConfig}
                    isDisabled={claudeSaving || !canEditRepo}
                    isLoading={claudeSaving}
                  >
                    保存配置
                  </Button>
                  <span className="text-default-400 text-xs">
                    {canEditRepo
                      ? '配置后，审查 PR 时将使用此仓库的 API Key'
                      : '组织仓库需要组织管理员权限才能修改 Claude 配置'}
                  </span>
                </div>
              </>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center">
                <GitPullRequest size={18} />
              </span>
              <h2 className="m-0 text-lg font-semibold">最新 Pull Requests</h2>
            </div>
            {!requiresLogin && !pullsLoading && pulls.length > 0 && (
              <Button isIconOnly variant="bordered" size="sm" onPress={fetchPulls} aria-label="刷新 PR">
                <RefreshCw size={16} className={pullsLoading ? 'animate-spin' : ''} />
              </Button>
            )}
          </CardHeader>
          <CardBody>
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
                      className="group flex items-center gap-3 p-3 rounded-xl border border-divider no-underline text-foreground transition-all hover:border-default-300 hover:bg-default-50"
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
                          <code className="bg-default-100 px-1.5 py-0.5 rounded text-[11px]">{pr.head.ref}</code>
                          <ChevronRight size={12} />
                          <code className="bg-default-100 px-1.5 py-0.5 rounded text-[11px]">{pr.base.ref}</code>
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
          </CardBody>
        </Card>
      </div>
    </>
  );
}

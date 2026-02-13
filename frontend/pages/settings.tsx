import Head from 'next/head';
import Image from 'next/image';
import { useCallback, useContext, useEffect, useState } from 'react';
import { Button, Chip, Input, addToast } from '@heroui/react';
import { Bot, User } from 'lucide-react';
import { AuthContext } from '../lib/auth';
import { apiFetch } from '../lib/api';
import PageHeader from '../components/PageHeader';
import SectionHeader from '../components/SectionHeader';
import { GlobalClaudeConfig, PublicConfig, UsageSummary } from '../lib/types';

export default function SettingsPage() {
  const { status: authStatus } = useContext(AuthContext);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [stats, setStats] = useState<UsageSummary | null>(null);
  const [reviewCount, setReviewCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [globalClaude, setGlobalClaude] = useState<GlobalClaudeConfig | null>(null);
  const [globalClaudeLoading, setGlobalClaudeLoading] = useState(true);
  const [globalClaudeSaving, setGlobalClaudeSaving] = useState(false);
  const [globalBaseUrl, setGlobalBaseUrl] = useState('');
  const [globalAuthToken, setGlobalAuthToken] = useState('');

  const fetchGlobalClaude = useCallback(async () => {
    if (!authStatus.loggedIn) {
      setGlobalClaude(null);
      setGlobalClaudeLoading(false);
      return;
    }

    setGlobalClaudeLoading(true);
    try {
      const res = await apiFetch('/api/config/claude-global');
      if (res.ok) {
        const data: GlobalClaudeConfig = await res.json();
        setGlobalClaude(data);
        setGlobalBaseUrl(data.anthropic_base_url || '');
      } else {
        setGlobalClaude(null);
      }
    } catch (error) {
      console.error('Failed to fetch global Claude config:', error);
      setGlobalClaude(null);
    } finally {
      setGlobalClaudeLoading(false);
    }
  }, [authStatus.loggedIn]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const configRes = await apiFetch('/api/config/public');
        if (configRes.ok) {
          const configData = await configRes.json();
          setConfig(configData);
        }

        const statsRes = await apiFetch('/api/stats');
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData.summary);
          setReviewCount(statsData.details?.length || 0);
        }
      } catch (error) {
        console.error('Failed to fetch settings data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  useEffect(() => {
    fetchGlobalClaude();
  }, [fetchGlobalClaude]);

  const refreshStats = async () => {
    try {
      const statsRes = await apiFetch('/api/stats');
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData.summary);
        setReviewCount(statsData.details?.length || 0);
      }
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    }
  };

  const saveGlobalClaudeConfig = async () => {
    if (!authStatus.loggedIn) {
      addToast({ title: '请先登录后再配置', color: 'warning' });
      return;
    }

    setGlobalClaudeSaving(true);
    try {
      const res = await apiFetch('/api/config/claude-global', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          anthropic_base_url: globalBaseUrl || null,
          anthropic_auth_token: globalAuthToken || null,
        }),
      });

      const data = await res.json();
      if (res.ok) {
        addToast({ title: '全局 Claude 配置已保存', color: 'success' });
        setGlobalAuthToken('');
        setGlobalClaude({
          configured: !!(data.anthropic_base_url || data.has_auth_token),
          anthropic_base_url: data.anthropic_base_url,
          has_auth_token: data.has_auth_token,
        });
      } else {
        addToast({ title: data.detail || '保存失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '无法连接后端', color: 'danger' });
    } finally {
      setGlobalClaudeSaving(false);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
  };

  return (
    <>
      <Head>
        <title>用户中心 - Gitea PR Reviewer</title>
      </Head>
      <div className="max-w-[1100px] mx-auto">
        <div className="pb-4">
          <PageHeader title="用户中心" subtitle="查看账号、使用统计和全局 Claude 默认配置" />
        </div>

        <section className="py-5 border-t border-divider/60">
          <SectionHeader title="用户信息" icon={<User size={18} />} />
          <div className="mt-4">
            {authStatus.loggedIn && authStatus.user ? (
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-full overflow-hidden bg-default-100 flex items-center justify-center shrink-0">
                  {authStatus.user.avatar_url ? (
                    <Image
                      src={authStatus.user.avatar_url}
                      alt={authStatus.user.username || 'avatar'}
                      width={64}
                      height={64}
                    />
                  ) : (
                    <span className="text-2xl font-semibold text-foreground">
                      {(authStatus.user.username || 'U')[0].toUpperCase()}
                    </span>
                  )}
                </div>
                <div>
                  <h3 className="m-0">{authStatus.user.full_name || authStatus.user.username}</h3>
                  <p className="m-0 text-default-500 text-sm">@{authStatus.user.username}</p>
                  <p className="m-0 text-default-400 text-xs mt-1">Gitea: {config?.gitea_url || '...'}</p>
                </div>
              </div>
            ) : (
              <p className="text-default-500 m-0">未登录</p>
            )}
          </div>
        </section>

        <section className="py-5 border-t border-divider/60">
          <SectionHeader
            title="使用统计"
            actions={
              <Button variant="bordered" size="sm" onPress={refreshStats}>
                刷新
              </Button>
            }
          />
          <div className="mt-4">
            {loading ? (
              <p className="text-default-500 m-0">加载中...</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { value: reviewCount, label: 'PR 审查次数' },
                  { value: stats?.total_claude_calls || 0, label: 'Claude API 调用' },
                  {
                    value: formatNumber((stats?.total_input_tokens || 0) + (stats?.total_output_tokens || 0)),
                    label: '总 Token 使用量',
                  },
                  { value: stats?.total_gitea_calls || 0, label: 'Gitea API 调用' },
                ].map(({ value, label }) => (
                  <div key={label} className="text-center">
                    <div className="text-2xl font-bold text-foreground">{value}</div>
                    <div className="text-sm text-default-500 mt-1">{label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="py-5 border-t border-divider/60">
          <SectionHeader title="服务状态" />
          <div className="mt-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-default-500 text-sm">Bot 用户名</span>
              <span className="text-sm font-medium">
                {config?.bot_username || <span className="text-default-400">未配置</span>}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-default-500 text-sm">Debug 模式</span>
              <Chip size="sm" color={config?.debug ? 'success' : 'default'} variant="flat">
                {config?.debug ? '开启' : '关闭'}
              </Chip>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-default-500 text-sm">OAuth 登录</span>
              <Chip size="sm" color={config?.oauth_enabled ? 'success' : 'default'} variant="flat">
                {config?.oauth_enabled ? '已启用' : '未启用'}
              </Chip>
            </div>
          </div>
          <p className="text-default-400 text-xs mt-4 m-0">
            各仓库可在配置页选择“与全局设置保持一致”，仅在需要时单独覆盖
          </p>
        </section>

        <section className="py-5 border-t border-divider/60">
          <SectionHeader
            title="Claude 全局配置"
            icon={<Bot size={18} />}
            actions={
              globalClaude?.has_auth_token ? (
                <Chip size="sm" variant="flat" color="success">已配置 Token</Chip>
              ) : null
            }
          />
          <div className="mt-4">
            {!authStatus.loggedIn ? (
              <p className="text-default-500 m-0">登录后可配置全局 Claude 设置</p>
            ) : globalClaudeLoading ? (
              <p className="text-default-500 m-0">加载中...</p>
            ) : (
              <>
                <div className="flex flex-col gap-3">
                  <Input
                    label="Base URL"
                    value={globalBaseUrl}
                    onValueChange={setGlobalBaseUrl}
                    placeholder="https://api.anthropic.com (留空使用默认)"
                    variant="bordered"
                  />
                  <Input
                    label="API Key"
                    type="password"
                    value={globalAuthToken}
                    onValueChange={setGlobalAuthToken}
                    placeholder={globalClaude?.has_auth_token ? '已配置（输入新值覆盖）' : 'sk-ant-...'}
                    variant="bordered"
                  />
                </div>
                <div className="mt-4 flex items-center gap-3 flex-wrap">
                  <Button
                    color="primary"
                    onPress={saveGlobalClaudeConfig}
                    isDisabled={globalClaudeSaving}
                    isLoading={globalClaudeSaving}
                  >
                    保存全局配置
                  </Button>
                  <span className="text-default-400 text-xs">
                    默认给所有仓库使用；仓库页可关闭继承并单独覆盖
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

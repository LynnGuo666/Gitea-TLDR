import Head from 'next/head';
import Image from 'next/image';
import { useContext, useEffect, useState } from 'react';
import { Button, Card, CardBody, CardHeader, Chip } from '@heroui/react';
import { User } from 'lucide-react';
import { AuthContext } from '../lib/auth';
import { PublicConfig, UsageSummary } from '../lib/types';

export default function SettingsPage() {
  const { status: authStatus } = useContext(AuthContext);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [stats, setStats] = useState<UsageSummary | null>(null);
  const [reviewCount, setReviewCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const configRes = await fetch('/api/config/public');
        if (configRes.ok) {
          const configData = await configRes.json();
          setConfig(configData);
        }

        const statsRes = await fetch('/api/stats');
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

  const refreshStats = async () => {
    try {
      const statsRes = await fetch('/api/stats');
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData.summary);
        setReviewCount(statsData.details?.length || 0);
      }
    } catch (error) {
      console.error('Failed to refresh stats:', error);
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
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <Card>
          <CardHeader className="flex items-center gap-2.5">
            <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center">
              <User size={18} />
            </span>
            <h2 className="m-0 text-lg font-semibold">用户信息</h2>
          </CardHeader>
          <CardBody>
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
                  <p className="m-0 text-default-400 text-xs mt-1">
                    Gitea: {config?.gitea_url || '...'}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-default-500 m-0">未登录</p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="flex items-center justify-between">
            <h2 className="m-0 text-lg font-semibold">使用统计</h2>
            <Button variant="bordered" size="sm" onPress={refreshStats}>
              刷新
            </Button>
          </CardHeader>
          <CardBody>
            {loading ? (
              <p className="text-default-500 m-0">加载中...</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {[
                  { value: reviewCount, label: 'PR 审查次数' },
                  { value: stats?.total_claude_calls || 0, label: 'Claude API 调用' },
                  { value: formatNumber((stats?.total_input_tokens || 0) + (stats?.total_output_tokens || 0)), label: '总 Token 使用量' },
                  { value: stats?.total_gitea_calls || 0, label: 'Gitea API 调用' },
                ].map(({ value, label }) => (
                  <div key={label} className="text-center">
                    <div className="text-2xl font-bold text-foreground">{value}</div>
                    <div className="text-sm text-default-500 mt-1">{label}</div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="m-0 text-lg font-semibold">服务状态</h2>
          </CardHeader>
          <CardBody>
            <div className="flex flex-col gap-3">
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
              Claude 配置（Base URL / API Key）请在各仓库的配置页面中单独设置
            </p>
          </CardBody>
        </Card>
      </div>
    </>
  );
}

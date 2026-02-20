import Head from 'next/head';
import Image from 'next/image';
import Link from 'next/link';
import { useContext, useEffect, useState } from 'react';
import { Button } from '@heroui/react';
import { Settings2, User } from 'lucide-react';
import { AuthContext } from '../lib/auth';
import { apiFetch } from '../lib/api';
import PageHeader from '../components/PageHeader';
import SectionHeader from '../components/SectionHeader';
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
        const [configRes, statsRes] = await Promise.all([
          apiFetch('/api/config/public'),
          apiFetch('/api/stats'),
        ]);

        if (configRes.ok) {
          const configData = await configRes.json();
          setConfig(configData);
        }

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
          <PageHeader
            title="用户中心"
            subtitle="查看账号与使用统计"
            actions={
              <Link href="/preferences" className="no-underline">
                <Button size="sm" variant="bordered" startContent={<Settings2 size={16} />}>
                  个人设置
                </Button>
              </Link>
            }
          />
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
                  { value: stats?.total_provider_calls || stats?.total_claude_calls || 0, label: '审查引擎调用' },
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

      </div>
    </>
  );
}

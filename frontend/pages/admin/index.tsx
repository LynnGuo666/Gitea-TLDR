import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState } from 'react';
import { Button, Chip } from '@heroui/react';
import { BarChart3, FolderGit2, Coins, Activity, RefreshCw, Settings, BookOpen, Webhook, Users } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import SectionHeader from '../../components/SectionHeader';
import { AuthContext } from '../../lib/auth';
import { apiFetch } from '../../lib/api';
import { PublicConfig } from '../../lib/types';

type DashboardStats = {
  database_available?: boolean;
  reviews: {
    total: number;
    today: number;
    week: number;
    month: number;
  };
  tokens: {
    total: number;
    today: number;
    week: number;
    month: number;
  };
  webhooks: {
    total: number;
    today: number;
    success_rate: number;
  };
  repositories: {
    total: number;
    active: number;
  };
};

export default function AdminDashboard() {
  const router = useRouter();
  const { status: authStatus } = useContext(AuthContext);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [databaseAvailable, setDatabaseAvailable] = useState(true);
  const [config, setConfig] = useState<PublicConfig | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, configRes] = await Promise.all([
        apiFetch('/api/admin/dashboard/stats'),
        apiFetch('/api/config/public'),
      ]);

      if (statsRes.status === 401 || statsRes.status === 403) {
        setStats(null);
        setError('当前账号没有管理后台权限');
        return;
      }
      if (!statsRes.ok) {
        throw new Error('获取统计数据失败');
      }

      if (configRes.ok) {
        const configData = await configRes.json();
        setConfig(configData);
      }

      const data = await statsRes.json();
      setStats(data);
      setDatabaseAvailable(data?.database_available ?? true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authStatus.loggedIn) {
      fetchStats();
    }
  }, [authStatus.loggedIn]);

  if (!authStatus.loggedIn) {
    return (
      <div className="max-w-[1100px] mx-auto">
        <div className="rounded-lg border border-default-200 px-4 py-6 text-center sm:px-6">
          <h1 className="m-0 page-title">管理后台</h1>
          <p className="text-default-500 m-0 mt-2">需要登录后才能访问管理后台</p>
        </div>
      </div>
    );
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toLocaleString();
  };

  const showDatabaseWarning = stats && !databaseAvailable;

  return (
    <>
      <Head>
        <title>管理后台 - Dashboard</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="管理后台"
          actions={
            <Button
              isIconOnly
              variant="bordered"
              size="sm"
              onPress={fetchStats}
              isDisabled={loading}
              aria-label="刷新统计"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </Button>
          }
        />

        {error && (
          <div className="p-3 bg-danger-50 border border-danger rounded-lg text-danger text-sm">
            {error}
          </div>
        )}

        {showDatabaseWarning && (
          <div className="p-3 bg-warning-50 border border-warning rounded-lg text-warning text-sm">
            数据库未启用，当前展示的是空统计数据。请检查 `DATABASE_URL` 或 `WORK_DIR` 配置并重启服务。
          </div>
        )}

        {loading && !stats ? (
          <div className="py-8 text-center rounded-lg border border-default-200">
            <p className="text-default-500 m-0">加载中...</p>
          </div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded-lg border border-default-200 p-4">
                <div className="flex items-center gap-2 text-default-500 mb-2">
                  <BarChart3 size={20} />
                  <h3 className="m-0 text-sm font-medium">审查次数</h3>
                </div>
                <div className="text-2xl font-bold text-foreground">{formatNumber(stats.reviews.total)}</div>
                <div className="flex gap-3 mt-2 text-xs text-default-400">
                  <span>今日: {stats.reviews.today}</span>
                  <span>本周: {stats.reviews.week}</span>
                  <span>本月: {stats.reviews.month}</span>
                </div>
              </div>

              <div className="rounded-lg border border-default-200 p-4">
                <div className="flex items-center gap-2 text-default-500 mb-2">
                  <Coins size={20} />
                  <h3 className="m-0 text-sm font-medium">Token 消耗</h3>
                </div>
                <div className="text-2xl font-bold text-foreground">{formatNumber(stats.tokens.total)}</div>
                <div className="flex gap-3 mt-2 text-xs text-default-400">
                  <span>今日: {formatNumber(stats.tokens.today)}</span>
                  <span>本周: {formatNumber(stats.tokens.week)}</span>
                  <span>本月: {formatNumber(stats.tokens.month)}</span>
                </div>
              </div>

              <div className="rounded-lg border border-default-200 p-4">
                <div className="flex items-center gap-2 text-default-500 mb-2">
                  <Activity size={20} />
                  <h3 className="m-0 text-sm font-medium">Webhook</h3>
                </div>
                <div className="text-2xl font-bold text-foreground">{stats.webhooks.total}</div>
                <div className="flex gap-3 mt-2 text-xs text-default-400">
                  <span>今日: {stats.webhooks.today}</span>
                  <span>成功率: {stats.webhooks.success_rate.toFixed(1)}%</span>
                </div>
              </div>

              <div className="rounded-lg border border-default-200 p-4">
                <div className="flex items-center gap-2 text-default-500 mb-2">
                  <FolderGit2 size={20} />
                  <h3 className="m-0 text-sm font-medium">仓库</h3>
                </div>
                <div className="text-2xl font-bold text-foreground">{stats.repositories.total}</div>
                <div className="flex gap-3 mt-2 text-xs text-default-400">
                  <span>活跃: {stats.repositories.active}</span>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-default-200 p-4 sm:p-5">
              <SectionHeader title="服务状态" className="mb-4" />
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
            </div>

            <div className="rounded-lg border border-default-200 p-4 sm:p-5">
              <SectionHeader title="快捷操作" className="mb-4" />
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[
                  { href: '/admin/config', icon: Settings, title: '全局配置', desc: '管理系统配置' },
                  { href: '/admin/repos', icon: FolderGit2, title: '仓库管理', desc: '批量操作仓库' },
                  { href: '/admin/reviews', icon: BookOpen, title: '审查历史', desc: '查看所有审查记录' },
                  { href: '/admin/webhooks', icon: Webhook, title: 'Webhook 日志', desc: '查看请求日志' },
                  { href: '/admin/users', icon: Users, title: '用户管理', desc: '管理管理员账户与权限' },
                ].map(({ href, icon: Icon, title, desc }) => (
                  <button
                    key={href}
                    className="text-left p-4 rounded-lg border border-default-200 bg-content1 cursor-pointer transition-colors hover:bg-default-100"
                    onClick={() => router.push(href)}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon size={16} className="text-default-500" />
                      <h3 className="m-0 text-sm font-semibold">{title}</h3>
                    </div>
                    <p className="m-0 text-xs text-default-500">{desc}</p>
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="py-8 text-center rounded-lg border border-default-200 text-default-500">
            暂无统计数据
          </div>
        )}
      </div>
    </>
  );
}

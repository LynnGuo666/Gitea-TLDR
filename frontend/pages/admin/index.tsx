import Head from 'next/head';
import { useRouter } from 'next/router';
import { useContext, useEffect, useState } from 'react';
import { Button, Card, CardBody, CardHeader } from '@heroui/react';
import { BarChart3, FolderGit2, Coins, Activity, RefreshCw, Settings, BookOpen, Webhook } from 'lucide-react';
import { AuthContext } from '../../lib/auth';

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

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/admin/dashboard/stats');
      if (res.status === 401 || res.status === 403) {
        router.push('/');
        return;
      }
      if (!res.ok) {
        throw new Error('获取统计数据失败');
      }
      const data = await res.json();
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
        <Card>
          <CardBody>
            <h1 className="m-0">管理后台</h1>
            <p className="text-default-500 m-0 mt-2">需要登录后才能访问管理后台</p>
          </CardBody>
        </Card>
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
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h1 className="m-0 text-xl font-semibold">管理后台</h1>
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
          </CardHeader>
          <CardBody>
            {error && (
              <div className="p-3 bg-danger-50 border border-danger rounded-lg text-danger text-sm mb-4">
                {error}
              </div>
            )}

            {showDatabaseWarning && (
              <div className="p-3 bg-warning-50 border border-warning rounded-lg text-warning text-sm mb-4">
                数据库未启用，当前展示的是空统计数据。请检查 `DATABASE_URL` 或 `WORK_DIR` 配置并重启服务。
              </div>
            )}

            {loading && !stats ? (
              <div className="py-8 text-center">
                <p className="text-default-500 m-0">加载中...</p>
              </div>
            ) : stats ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="border border-divider rounded-xl p-4">
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

                  <div className="border border-divider rounded-xl p-4">
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

                  <div className="border border-divider rounded-xl p-4">
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

                  <div className="border border-divider rounded-xl p-4">
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

                <div className="mt-8">
                  <h2 className="m-0 mb-4 text-base font-semibold">快捷操作</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {[
                      { href: '/admin/config', icon: Settings, title: '全局配置', desc: '管理系统配置' },
                      { href: '/admin/repos', icon: FolderGit2, title: '仓库管理', desc: '批量操作仓库' },
                      { href: '/admin/reviews', icon: BookOpen, title: '审查历史', desc: '查看所有审查记录' },
                      { href: '/admin/webhooks', icon: Webhook, title: 'Webhook 日志', desc: '查看请求日志' },
                    ].map(({ href, icon: Icon, title, desc }) => (
                      <button
                        key={href}
                        className="text-left p-4 rounded-xl border border-divider bg-transparent cursor-pointer transition-all hover:border-default-300 hover:bg-default-50 hover:-translate-y-0.5 hover:shadow-sm"
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
            ) : null}
          </CardBody>
        </Card>
      </div>
    </>
  );
}

import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from '@heroui/react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';

type ManagedRepo = {
  id: number;
  owner: string;
  repo_name: string;
  full_name: string;
  is_active: boolean;
  has_webhook_secret: boolean;
  created_at: string | null;
  updated_at: string | null;
};

type ReposResponse = {
  repositories: ManagedRepo[];
};

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminReposPage() {
  const [repos, setRepos] = useState<ManagedRepo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');

  const fetchRepos = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await apiFetch('/api/repositories');
      if (!res.ok) {
        if (res.status === 503) {
          throw new Error('数据库未启用，无法读取仓库信息');
        }
        throw new Error('获取仓库列表失败');
      }
      const data = (await res.json()) as ReposResponse;
      setRepos(data.repositories || []);
    } catch (err) {
      setRepos([]);
      setError(err instanceof Error ? err.message : '获取仓库列表失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchRepos();
  }, [fetchRepos]);

  const filteredRepos = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return repos.filter((repo) => {
      if (statusFilter === 'active' && !repo.is_active) return false;
      if (statusFilter === 'inactive' && repo.is_active) return false;
      if (!normalizedQuery) return true;
      return repo.full_name.toLowerCase().includes(normalizedQuery);
    });
  }, [repos, query, statusFilter]);

  const activeCount = useMemo(() => repos.filter((repo) => repo.is_active).length, [repos]);

  return (
    <>
      <Head>
        <title>仓库管理 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="仓库管理"
          actions={
            <div className="flex items-center gap-2">
              <Button
                isIconOnly
                variant="bordered"
                size="sm"
                onPress={() => fetchRepos(true)}
                isDisabled={refreshing || loading}
                aria-label="刷新仓库列表"
              >
                <RefreshCw size={16} className={refreshing || loading ? 'animate-spin' : ''} />
              </Button>
              <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
                返回管理后台
              </Button>
            </div>
          }
        />

        {error ? <div className="rounded-lg border border-danger-200 bg-danger-50 p-3 text-danger-700 text-sm">{error}</div> : null}

        <section className="rounded-lg border border-default-200 p-4 sm:p-5 flex flex-col gap-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-lg border border-default-200 p-3">
              <div className="text-xs text-default-500">仓库总数</div>
              <div className="mt-1 text-xl font-semibold">{repos.length}</div>
            </div>
            <div className="rounded-lg border border-default-200 p-3">
              <div className="text-xs text-default-500">已启用</div>
              <div className="mt-1 text-xl font-semibold">{activeCount}</div>
            </div>
            <div className="rounded-lg border border-default-200 p-3">
              <div className="text-xs text-default-500">未启用</div>
              <div className="mt-1 text-xl font-semibold">{Math.max(0, repos.length - activeCount)}</div>
            </div>
            <div className="rounded-lg border border-default-200 p-3">
              <div className="text-xs text-default-500">已配置 Secret</div>
              <div className="mt-1 text-xl font-semibold">{repos.filter((repo) => repo.has_webhook_secret).length}</div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <input
              className="rounded-md border border-default-200 bg-content1 px-3 py-2 min-w-64"
              placeholder="搜索仓库（owner/repo）"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              className="rounded-md border border-default-200 bg-content1 px-2 py-2"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
            >
              <option value="all">全部状态</option>
              <option value="active">已启用</option>
              <option value="inactive">未启用</option>
            </select>
            <span className="text-sm text-default-500">结果: {filteredRepos.length}</span>
          </div>

          {loading ? (
            <div className="py-10 text-center text-default-500">加载仓库列表中...</div>
          ) : filteredRepos.length === 0 ? (
            <div className="py-10 text-center text-default-500">没有匹配的仓库</div>
          ) : (
            <div className="rounded-lg border border-default-200 overflow-hidden">
              <Table aria-label="仓库管理表" removeWrapper>
                <TableHeader>
                  <TableColumn>仓库</TableColumn>
                  <TableColumn>状态</TableColumn>
                  <TableColumn>Webhook Secret</TableColumn>
                  <TableColumn>更新时间</TableColumn>
                  <TableColumn>操作</TableColumn>
                </TableHeader>
                <TableBody>
                  {filteredRepos.map((repo) => (
                    <TableRow key={repo.id}>
                      <TableCell>
                        <div className="font-medium">{repo.full_name}</div>
                        <div className="text-xs text-default-400">ID: {repo.id}</div>
                      </TableCell>
                      <TableCell>
                        <Chip size="sm" color={repo.is_active ? 'success' : 'default'} variant="flat">
                          {repo.is_active ? '已启用' : '未启用'}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        <Chip size="sm" color={repo.has_webhook_secret ? 'success' : 'warning'} variant="flat">
                          {repo.has_webhook_secret ? '已配置' : '未配置'}
                        </Chip>
                      </TableCell>
                      <TableCell>{formatTime(repo.updated_at)}</TableCell>
                      <TableCell>
                        <Button as={Link} href={`/repo/${repo.owner}/${repo.repo_name}`} size="sm" variant="bordered">
                          打开
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

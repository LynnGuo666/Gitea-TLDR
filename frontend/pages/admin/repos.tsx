import Head from 'next/head';
import PageHeader from '../../components/PageHeader';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import { useApiFetch } from '../../lib/hooks';
import { Repository } from '../../lib/types';

export default function AdminReposPage() {
  const { data, loading, error, refresh } = useApiFetch<{ repos: Repository[] }>('/api/v2/repos');
  const repos = data?.repos || [];

  return (
    <>
      <Head><title>Repositories - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Repositories" subtitle="当前可访问仓库" />
        <div className="mt-4 grid gap-2">
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={refresh} className="text-sm text-primary hover:underline">重试</button>} />
          ) : repos.length === 0 ? (
            <EmptyState title="暂无仓库" description="尚未注册任何仓库。触发 webhook 或在首页添加仓库后会自动登记。" />
          ) : (
            repos.map((repo) => <div key={repo.full_name || repo.id} className="border-b border-divider py-2">{repo.full_name || repo.name}</div>)
          )}
        </div>
      </div>
    </>
  );
}

import Head from 'next/head';
import { useEffect, useState } from 'react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';
import { Repository } from '../../lib/types';

export default function AdminReposPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  useEffect(() => {
    apiFetch('/api/v2/repos').then((res) => res.json()).then((data) => setRepos(data.repos || [])).catch(() => setRepos([]));
  }, []);
  return (
    <>
      <Head><title>Repositories - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Repositories" subtitle="当前可访问仓库" />
        <div className="mt-4 grid gap-2">
          {repos.map((repo) => <div key={repo.full_name || repo.id} className="border-b border-divider py-2">{repo.full_name || repo.name}</div>)}
        </div>
      </div>
    </>
  );
}

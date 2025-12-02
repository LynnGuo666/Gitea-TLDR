import Head from 'next/head';
import { useEffect, useState } from 'react';
import RepoList from '../components/RepoList';
import { Repo } from '../lib/types';

export default function Home() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch('/api/repos')
      .then((res) => res.json())
      .then((data) => {
        setRepos(data.repos || []);
        setLoading(false);
      })
      .catch(() => {
        setRepos([]);
        setLoading(false);
      });
  }, []);

  return (
    <>
      <Head>
        <title>仪表盘 - Gitea PR Reviewer</title>
      </Head>
      <main className="dashboard">
        <section className="card">
          <div className="panel-header">
            <h2>我的仓库</h2>
            <span className="badge-soft">
              {loading ? '加载中...' : `${repos.length} 个仓库`}
            </span>
          </div>
          {loading ? (
            <div className="empty-state">
              <p>加载中...</p>
            </div>
          ) : (
            <RepoList repos={repos} />
          )}
        </section>
      </main>
    </>
  );
}

import Head from 'next/head';
import { useContext, useEffect, useState } from 'react';
import RepoList from '../components/RepoList';
import { Repo } from '../lib/types';
import { AuthContext } from '../lib/auth';

export default function Home() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [needsAuth, setNeedsAuth] = useState(false);
  const { status: authStatus, beginLogin } = useContext(AuthContext);

  useEffect(() => {
    if (authStatus.enabled && !authStatus.loggedIn) {
      setRepos([]);
      setNeedsAuth(true);
      setLoading(false);
      return;
    }

    setLoading(true);
    fetch('/api/repos')
      .then(async (res) => {
        if (res.status === 401) {
          setNeedsAuth(true);
          setRepos([]);
          setLoading(false);
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        setNeedsAuth(false);
        setRepos(data.repos || []);
        setLoading(false);
      })
      .catch(() => {
        setRepos([]);
        setLoading(false);
        setNeedsAuth(false);
      });
  }, [authStatus.enabled, authStatus.loggedIn]);

  const repoCountLabel = needsAuth
    ? '等待登录'
    : loading
    ? '同步中...'
    : `${repos.length} 个仓库`;
  return (
    <>
      <Head>
        <title>仪表盘 - Gitea PR Reviewer</title>
      </Head>
      <main className="dashboard home-dashboard">
        <section className="repo-section">
          <div className="repo-section-header">
            <h2>我的仓库</h2>
            <span className="repo-count-badge">{repoCountLabel}</span>
          </div>
          {needsAuth ? (
            <div className="empty-state">
              <p>请先连接 Gitea，才可同步仓库列表。</p>
              <button className="primary-button" onClick={beginLogin}>
                使用 Gitea 登录
              </button>
            </div>
          ) : loading ? (
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

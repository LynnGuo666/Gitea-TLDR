import Head from 'next/head';
import { useContext, useEffect, useState, useMemo } from 'react';
import RepoList from '../components/RepoList';
import { RepoSkeleton } from '../components/ui';
import { SearchIcon, RefreshIcon, RepoIcon } from '../components/icons';
import { Repo } from '../lib/types';
import { AuthContext } from '../lib/auth';
import { useDebounce } from '../lib/hooks';

export default function Home() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [ownerFilter, setOwnerFilter] = useState<'all' | 'personal' | 'org'>('all');
  const [readonlyFilter, setReadonlyFilter] = useState<'all' | 'readonly' | 'writable'>('all');
  const { status: authStatus, beginLogin } = useContext(AuthContext);

  const debouncedSearch = useDebounce(searchQuery, 300);

  const fetchRepos = async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);

    try {
      const res = await fetch('/api/repos');
      if (res.status === 401) {
        setNeedsAuth(true);
        setRepos([]);
      } else {
        const data = await res.json();
        setNeedsAuth(false);
        setRepos(data.repos || []);
      }
    } catch {
      setRepos([]);
      setNeedsAuth(false);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (authStatus.enabled && !authStatus.loggedIn) {
      setRepos([]);
      setNeedsAuth(true);
      setLoading(false);
      return;
    }
    fetchRepos();
  }, [authStatus.enabled, authStatus.loggedIn]);

  const filteredRepos = useMemo(() => {
    let filtered = repos;

    // 应用所有者筛选
    if (ownerFilter !== 'all') {
      const currentUser = authStatus.user?.username;
      filtered = filtered.filter(repo => {
        const owner = repo.owner?.username || repo.owner?.login;
        if (ownerFilter === 'personal') {
          return owner === currentUser;
        } else {
          return owner !== currentUser;
        }
      });
    }

    // 应用只读筛选
    if (readonlyFilter !== 'all') {
      filtered = filtered.filter(repo => {
        const isReadOnly = !repo.permissions?.admin;
        if (readonlyFilter === 'readonly') {
          return isReadOnly;
        } else {
          return !isReadOnly;
        }
      });
    }

    // 应用搜索筛选
    if (!debouncedSearch.trim()) return filtered;
    const query = debouncedSearch.toLowerCase();
    return filtered.filter((repo) => {
      const fullName = repo.full_name || `${repo.owner?.username || repo.owner?.login}/${repo.name}`;
      return fullName.toLowerCase().includes(query);
    });
  }, [repos, debouncedSearch, ownerFilter, readonlyFilter, authStatus.user]);

  const repoCountLabel = needsAuth
    ? '等待登录'
    : loading
    ? '同步中...'
    : `${filteredRepos.length} 个仓库${debouncedSearch ? ` (筛选自 ${repos.length})` : ''}`;

  return (
    <>
      <Head>
        <title>仪表盘 - Gitea PR Reviewer</title>
      </Head>
      <main className="dashboard home-dashboard">
        <section className="repo-section">
          <div className="repo-section-header">
            <h2>我的仓库</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="repo-count-badge">{repoCountLabel}</span>
              {!needsAuth && !loading && (
                <>
                  <button
                    className={`refresh-button ${refreshing ? 'spinning' : ''}`}
                    onClick={() => fetchRepos(true)}
                    disabled={refreshing}
                    title="刷新仓库列表"
                  >
                    <RefreshIcon size={18} />
                  </button>
                  <select
                    className="filter-select"
                    value={ownerFilter}
                    onChange={(e) => setOwnerFilter(e.target.value as 'all' | 'personal' | 'org')}
                    disabled={refreshing}
                  >
                    <option value="all">全部</option>
                    <option value="personal">个人仓库</option>
                    <option value="org">组织仓库</option>
                  </select>
                  <select
                    className="filter-select"
                    value={readonlyFilter}
                    onChange={(e) => setReadonlyFilter(e.target.value as 'all' | 'readonly' | 'writable')}
                    disabled={refreshing}
                  >
                    <option value="all">全部权限</option>
                    <option value="writable">可管理</option>
                    <option value="readonly">只读</option>
                  </select>
                </>
              )}
            </div>
          </div>

          {needsAuth ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <RepoIcon size={32} />
              </div>
              <h3>连接 Gitea 以开始</h3>
              <p>请先连接 Gitea，才可同步仓库列表。</p>
              <button className="primary-button" onClick={beginLogin}>
                使用 Gitea 登录
              </button>
            </div>
          ) : loading ? (
            <RepoSkeleton />
          ) : (
            <>
              {repos.length > 3 && (
                <div className="search-container">
                  <SearchIcon size={18} className="search-icon" />
                  <input
                    type="text"
                    className="search-input"
                    placeholder="搜索仓库..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              )}
              {filteredRepos.length === 0 && debouncedSearch ? (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <SearchIcon size={32} />
                  </div>
                  <h3>未找到匹配的仓库</h3>
                  <p>尝试使用不同的搜索词</p>
                </div>
              ) : (
                <RepoList repos={filteredRepos} />
              )}
            </>
          )}
        </section>
      </main>
    </>
  );
}

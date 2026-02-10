import Head from 'next/head';
import { useContext, useEffect, useState, useMemo } from 'react';
import { Button, Input, Select, SelectItem } from '@heroui/react';
import { Search, RefreshCw, FolderGit2 } from 'lucide-react';
import RepoList from '../components/RepoList';
import { RepoSkeleton } from '../components/ui';
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

    if (ownerFilter !== 'all') {
      const currentUser = authStatus.user?.username;
      filtered = filtered.filter(repo => {
        const owner = repo.owner?.username || repo.owner?.login;
        return ownerFilter === 'personal' ? owner === currentUser : owner !== currentUser;
      });
    }

    if (readonlyFilter !== 'all') {
      filtered = filtered.filter(repo => {
        const isReadOnly = !repo.permissions?.admin;
        return readonlyFilter === 'readonly' ? isReadOnly : !isReadOnly;
      });
    }

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
      <div className="max-w-[1100px] mx-auto flex flex-col gap-8">
        <section className="flex flex-col gap-6">
          <div className="flex items-end justify-between flex-wrap gap-2.5">
            <h2 className="m-0">我的仓库</h2>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-dashed border-default-300 px-4 py-1.5 text-sm text-default-500">
                {repoCountLabel}
              </span>
              {!needsAuth && !loading && (
                <>
                  <Button
                    isIconOnly
                    variant="bordered"
                    size="sm"
                    onPress={() => fetchRepos(true)}
                    isDisabled={refreshing}
                    aria-label="刷新仓库列表"
                  >
                    <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
                  </Button>
                  <Select
                    size="sm"
                    selectedKeys={new Set([ownerFilter])}
                    onSelectionChange={(keys) => {
                      if (keys === 'all') return;
                      const key = Array.from(keys)[0] as string;
                      if (key) setOwnerFilter(key as 'all' | 'personal' | 'org');
                    }}
                    isDisabled={refreshing}
                    className="w-32"
                    aria-label="所有者筛选"
                  >
                    <SelectItem key="all">全部</SelectItem>
                    <SelectItem key="personal">个人仓库</SelectItem>
                    <SelectItem key="org">组织仓库</SelectItem>
                  </Select>
                  <Select
                    size="sm"
                    selectedKeys={new Set([readonlyFilter])}
                    onSelectionChange={(keys) => {
                      if (keys === 'all') return;
                      const key = Array.from(keys)[0] as string;
                      if (key) setReadonlyFilter(key as 'all' | 'readonly' | 'writable');
                    }}
                    isDisabled={refreshing}
                    className="w-32"
                    aria-label="权限筛选"
                  >
                    <SelectItem key="all">全部权限</SelectItem>
                    <SelectItem key="writable">可管理</SelectItem>
                    <SelectItem key="readonly">只读</SelectItem>
                  </Select>
                </>
              )}
            </div>
          </div>

          {needsAuth ? (
            <div className="flex flex-col items-center justify-center py-12 text-default-500 gap-4">
              <div className="w-16 h-16 rounded-xl bg-default-100 flex items-center justify-center text-default-400">
                <FolderGit2 size={32} />
              </div>
              <h3 className="m-0 text-foreground">连接 Gitea 以开始</h3>
              <p className="m-0 text-sm">请先连接 Gitea，才可同步仓库列表。</p>
              <Button color="primary" onPress={beginLogin}>
                使用 Gitea 登录
              </Button>
            </div>
          ) : loading ? (
            <RepoSkeleton />
          ) : (
            <>
              {repos.length > 3 && (
                <Input
                  placeholder="搜索仓库..."
                  value={searchQuery}
                  onValueChange={setSearchQuery}
                  startContent={<Search size={18} className="text-default-400" />}
                  size="lg"
                  variant="bordered"
                  radius="lg"
                />
              )}
              {filteredRepos.length === 0 && debouncedSearch ? (
                <div className="flex flex-col items-center justify-center py-12 text-default-500 gap-4">
                  <div className="w-16 h-16 rounded-xl bg-default-100 flex items-center justify-center text-default-400">
                    <Search size={32} />
                  </div>
                  <h3 className="m-0 text-foreground">未找到匹配的仓库</h3>
                  <p className="m-0 text-sm">尝试使用不同的搜索词</p>
                </div>
              ) : (
                <RepoList repos={filteredRepos} />
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}

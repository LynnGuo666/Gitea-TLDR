import Link from 'next/link';
import { useRouter } from 'next/router';
import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import {
  Button,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Avatar,
} from '@heroui/react';
import { BarChart3, User, Sun, Moon, Shield, LogOut, LayoutGrid } from 'lucide-react';
import { VersionDisplay } from './VersionDisplay';
import {
  AuthContext,
  defaultAuthStatus,
  type AuthStatus,
  fetchAuthStatus,
  beginOAuthLogin,
  requestLogout,
} from '../lib/auth';
import { useWindowFocus } from '../lib/hooks';

type LayoutProps = {
  children: ReactNode;
};

const navItems = [
  { href: '/', label: '仪表盘', icon: LayoutGrid },
  { href: '/usage', label: '用量', icon: BarChart3 },
  { href: '/settings', label: '用户中心', icon: User },
  { href: '/admin', label: '管理后台', icon: Shield, adminOnly: true },
];

const AUTH_POLL_INTERVAL = 60000;
const AUTH_POLL_INTERVAL_FOCUSED = 30000;

function isAuthStatusEqual(a: AuthStatus, b: AuthStatus): boolean {
  return (
    a.enabled === b.enabled &&
    a.loggedIn === b.loggedIn &&
    (a.user?.username || '') === (b.user?.username || '') &&
    (a.user?.full_name || '') === (b.user?.full_name || '') &&
    (a.user?.avatar_url || '') === (b.user?.avatar_url || '')
  );
}

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();
  const [authStatus, setAuthStatus] = useState(defaultAuthStatus);
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const isWindowFocused = useWindowFocus();
  const authRefreshInFlightRef = useRef(false);

  useEffect(() => { setMounted(true); }, []);

  const refreshAuth = useCallback(() => {
    if (authRefreshInFlightRef.current) return;
    authRefreshInFlightRef.current = true;

    void fetchAuthStatus()
      .then((nextStatus) => {
        setAuthStatus((prevStatus) =>
          isAuthStatusEqual(prevStatus, nextStatus) ? prevStatus : nextStatus
        );
      })
      .catch(() => {
        setAuthStatus((prevStatus) =>
          isAuthStatusEqual(prevStatus, defaultAuthStatus) ? prevStatus : defaultAuthStatus
        );
      })
      .finally(() => {
        authRefreshInFlightRef.current = false;
      });
  }, []);

  useEffect(() => { refreshAuth(); }, [refreshAuth]);

  useEffect(() => {
    if (document.visibilityState !== 'visible') return;
    const interval = isWindowFocused ? AUTH_POLL_INTERVAL_FOCUSED : AUTH_POLL_INTERVAL;
    const id = setInterval(refreshAuth, interval);
    return () => clearInterval(id);
  }, [refreshAuth, isWindowFocused]);

  useEffect(() => {
    if (isWindowFocused) refreshAuth();
  }, [isWindowFocused, refreshAuth]);

  const beginLogin = useCallback(async () => {
    try { await beginOAuthLogin(); } catch (error) { console.error(error); }
  }, []);

  const logout = useCallback(async () => {
    await requestLogout();
    refreshAuth();
  }, [refreshAuth]);

  const authContextValue = useMemo(
    () => ({ status: authStatus, refresh: refreshAuth, beginLogin, logout }),
    [authStatus, refreshAuth, beginLogin, logout]
  );

  const requiresLogin = authStatus.enabled && !authStatus.loggedIn;

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <AuthContext.Provider value={authContextValue}>
      <div className="flex min-h-dvh">
        <aside className="w-full sm:w-60 sidebar-glass border-b sm:border-b-0 sm:border-r border-divider/50 flex sm:flex-col justify-between shrink-0">
          <div className="p-4 sm:px-5 sm:py-5 border-b border-divider flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5 font-semibold">
              <strong className="hidden sm:inline text-foreground">Gitea PR Reviewer</strong>
            </div>
            {mounted && (
              <Button
                isIconOnly
                variant="light"
                size="sm"
                onPress={toggleTheme}
                aria-label="切换主题"
              >
                {resolvedTheme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </Button>
            )}
          </div>
          <nav className="flex flex-row sm:flex-col overflow-x-auto sm:overflow-visible px-3 py-2 sm:py-4 gap-1 flex-1">
            {navItems.map((item) => {
              if (item.adminOnly && !authStatus.loggedIn) return null;
              const isExact = item.href === '/';
              const active = isExact
                ? router.pathname === '/'
                : router.pathname === item.href || router.pathname.startsWith(item.href + '/');
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm no-underline transition-colors whitespace-nowrap ${
                    active
                      ? 'bg-primary/10 font-semibold text-primary sm:border-l-3 sm:border-primary'
                      : 'text-foreground/80 hover:bg-default-100/60'
                  }`}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="hidden sm:block p-4 mt-auto">
            <VersionDisplay compact />
            {authStatus.enabled ? (
              authStatus.loggedIn ? (
                <Dropdown placement="top-start">
                  <DropdownTrigger>
                    <button className="w-full rounded-xl p-2.5 flex items-center gap-3 bg-default-100 cursor-pointer transition-colors hover:bg-default-200 text-left">
                      {authStatus.user?.avatar_url ? (
                        <Avatar
                          src={authStatus.user.avatar_url}
                          name={authStatus.user.username || 'U'}
                          size="sm"
                        />
                      ) : (
                        <Avatar
                          name={(authStatus.user?.username || 'U')[0]}
                          size="sm"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <strong className="block text-sm text-foreground truncate">
                          {authStatus.user?.full_name || authStatus.user?.username || '已登录'}
                        </strong>
                        <span className="block text-xs text-default-500 truncate">
                          @{authStatus.user?.username || ''}
                        </span>
                      </div>
                    </button>
                  </DropdownTrigger>
                  <DropdownMenu
                    aria-label="用户菜单"
                    onAction={(key) => {
                      if (key === 'logout') logout();
                    }}
                  >
                    <DropdownItem key="logout" startContent={<LogOut size={16} />}>
                      退出登录
                    </DropdownItem>
                  </DropdownMenu>
                </Dropdown>
              ) : (
                <Button
                  variant="bordered"
                  color="primary"
                  fullWidth
                  radius="full"
                  onPress={beginLogin}
                >
                  连接 PKUGit
                </Button>
              )
            ) : (
              <p className="text-sm text-default-500 m-0">请配置 OAuth 登录</p>
            )}
          </div>
        </aside>
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 sm:px-8 pb-12 bg-default-50">
          {!authStatus.enabled ? (
            <section className="max-w-lg mx-auto mt-16 text-center flex flex-col gap-4">
              <h1 className="m-0">需要配置 OAuth</h1>
              <p className="m-0 text-default-500">
                管理员需要在环境变量中配置 OAuth (OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_REDIRECT_URL) 才能使用本系统。
              </p>
            </section>
          ) : requiresLogin ? (
            <section className="max-w-lg mx-auto mt-16 text-center flex flex-col gap-4">
              <h1 className="m-0">连接 PKUGit</h1>
              <p className="m-0 text-default-500">
                需要先授权 PKUGit 帐号后，才能加载仓库列表与审查配置。
                该授权仅用于读取你有权限的仓库，并为其创建 Webhook。
              </p>
              <Button color="primary" onPress={beginLogin}>
                立即连接
              </Button>
            </section>
          ) : (
            children
          )}
        </main>
      </div>
    </AuthContext.Provider>
  );
}

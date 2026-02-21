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
import { BarChart3, User, Sun, Moon, Shield, LogOut, LayoutGrid, Menu, X, Settings2, BookOpen } from 'lucide-react';
import { VersionDisplay } from './VersionDisplay';
import {
  AuthContext,
  defaultAuthStatus,
  type AuthStatus,
  fetchAuthStatus,
  fetchAdminStatus,
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
  { href: '/reviews', label: '审查记录', icon: BookOpen },
  { href: '/settings', label: '用户中心', icon: User },
  { href: '/preferences', label: '个人设置', icon: Settings2 },
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
  const [isAdmin, setIsAdmin] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const isWindowFocused = useWindowFocus();
  const authRefreshInFlightRef = useRef(false);

  useEffect(() => { setMounted(true); }, []);

  const refreshAuth = useCallback(() => {
    if (authRefreshInFlightRef.current) return;
    authRefreshInFlightRef.current = true;

    void fetchAuthStatus()
      .then(async (nextStatus) => {
        setAuthStatus((prevStatus) =>
          isAuthStatusEqual(prevStatus, nextStatus) ? prevStatus : nextStatus
        );

        if (nextStatus.enabled && nextStatus.loggedIn) {
          try {
            const adminStatus = await fetchAdminStatus();
            setIsAdmin(adminStatus.enabled && adminStatus.loggedIn && adminStatus.isAdmin);
          } catch {
            setIsAdmin(false);
          }
          return;
        }

        setIsAdmin(false);
      })
      .catch(() => {
        setAuthStatus((prevStatus) =>
          isAuthStatusEqual(prevStatus, defaultAuthStatus) ? prevStatus : defaultAuthStatus
        );
        setIsAdmin(false);
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
    setIsAdmin(false);
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

  // 路由切换时自动关闭手机菜单
  useEffect(() => {
    const handleRouteChange = () => setMobileMenuOpen(false);
    router.events.on('routeChangeComplete', handleRouteChange);
    return () => router.events.off('routeChangeComplete', handleRouteChange);
  }, [router.events]);

  return (
    <AuthContext.Provider value={authContextValue}>
      <div className="flex flex-col sm:flex-row min-h-dvh">
        {/* ── 移动端：固定顶部栏 ── */}
        <header className="sm:hidden sticky top-0 z-50 sidebar-glass border-b border-divider/50 relative">
          <div className="flex items-center justify-between px-4 h-14">
            <div className="flex items-center gap-2.5 font-semibold">
              <strong className="text-foreground text-base">LCPU</strong>
            </div>
            <div className="flex items-center gap-1">
              {authStatus.enabled && (
                <Dropdown placement="bottom-end">
                  <DropdownTrigger>
                    <Button isIconOnly variant="light" size="sm" className="data-[hover=true]:bg-default/40">
                      {authStatus.loggedIn && authStatus.user?.avatar_url ? (
                        <Avatar
                          src={authStatus.user.avatar_url}
                          name={authStatus.user.username || 'U'}
                          className="w-6 h-6 text-tiny"
                        />
                      ) : (
                        <Avatar
                          name={(authStatus.user?.username || 'U')[0]}
                          className="w-6 h-6 text-tiny"
                        />
                      )}
                    </Button>
                  </DropdownTrigger>
                  <DropdownMenu
                    aria-label="用户菜单"
                    onAction={(key) => {
                      if (key === 'logout') logout();
                      if (key === 'login') beginLogin();
                    }}
                  >
                    <DropdownItem key="user-info" isReadOnly textValue="用户信息" className="h-14 gap-2 opacity-100 cursor-default">
                      <div className="font-semibold">
                        {authStatus.loggedIn ? (authStatus.user?.full_name || authStatus.user?.username) : '未登录'}
                      </div>
                      <div className="text-tiny text-default-500">
                        {authStatus.loggedIn ? `@${authStatus.user?.username}` : '点击下方登录'}
                      </div>
                    </DropdownItem>
                    <DropdownItem key="version" isReadOnly textValue="版本信息" className="cursor-default">
                      <VersionDisplay inline />
                    </DropdownItem>
                    {authStatus.loggedIn ? (
                      <DropdownItem key="logout" startContent={<LogOut size={16} />}>
                        退出登录
                      </DropdownItem>
                    ) : (
                      <DropdownItem key="login" startContent={<User size={16} />}>
                        连接 PKUGit
                      </DropdownItem>
                    )}
                  </DropdownMenu>
                </Dropdown>
              )}
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
              <Button
                isIconOnly
                variant="light"
                size="sm"
                onPress={() => setMobileMenuOpen((v) => !v)}
                aria-label={mobileMenuOpen ? '关闭菜单' : '打开菜单'}
              >
                {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
              </Button>
            </div>
          </div>

          <nav
            className={`absolute left-0 right-0 top-full border-b border-divider/50 sidebar-glass px-3 py-2 flex flex-col gap-1 shadow-md transition-all duration-200 ease-out origin-top ${
              mobileMenuOpen
                ? 'opacity-100 translate-y-0 pointer-events-auto'
                : 'opacity-0 -translate-y-1 pointer-events-none'
            }`}
            aria-hidden={!mobileMenuOpen}
          >
            {navItems.map((item) => {
              if (item.adminOnly && !isAdmin) return null;
              const isExact = item.href === '/';
              const active = isExact
                ? router.pathname === '/'
                : router.pathname === item.href || router.pathname.startsWith(item.href + '/');
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm no-underline transition-colors ${
                    active
                      ? 'bg-primary/10 font-semibold text-primary'
                      : 'text-foreground/80 hover:bg-default-100/60'
                  }`}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </header>

        {/* ── 桌面端：左侧侧边栏 ── */}
        <aside className="hidden sm:flex w-60 sidebar-glass border-r border-divider/50 flex-col justify-between shrink-0 h-dvh sticky top-0 self-start">
          <div className="px-5 py-5 border-b border-divider flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5 font-semibold">
              <strong className="text-foreground">LCPU AI Reviewer</strong>
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
          <nav className="flex flex-col overflow-visible py-4 px-3 gap-1 flex-1">
            {navItems.map((item) => {
              if (item.adminOnly && !isAdmin) return null;
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
                      ? 'bg-primary/10 font-semibold text-primary'
                      : 'text-foreground/80 hover:bg-default-100/60'
                  }`}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="p-4 mt-auto">
            {authStatus.enabled ? (
              <Dropdown placement="top-start">
                <DropdownTrigger>
                  <button className="w-full rounded-xl p-2.5 flex items-center gap-3 cursor-pointer transition-colors hover:bg-default-100 text-left">
                    {authStatus.loggedIn && authStatus.user?.avatar_url ? (
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
                        {authStatus.loggedIn
                          ? authStatus.user?.full_name || authStatus.user?.username || '已登录'
                          : '未登录'}
                      </strong>
                      <span className="block text-xs text-default-500 truncate">
                        {authStatus.loggedIn ? `@${authStatus.user?.username || ''}` : '点击登录'}
                      </span>
                    </div>
                  </button>
                </DropdownTrigger>
                <DropdownMenu
                  aria-label="用户菜单"
                  onAction={(key) => {
                    if (key === 'logout') logout();
                    if (key === 'login') beginLogin();
                  }}
                >
                  <DropdownItem key="version" isReadOnly textValue="版本信息" className="cursor-default">
                    <VersionDisplay inline />
                  </DropdownItem>
                  {authStatus.loggedIn ? (
                    <DropdownItem key="logout" startContent={<LogOut size={16} />}>
                      退出登录
                    </DropdownItem>
                  ) : (
                    <DropdownItem key="login" startContent={<User size={16} />}>
                      连接 PKUGit
                    </DropdownItem>
                  )}
                </DropdownMenu>
              </Dropdown>
            ) : (
              <p className="text-sm text-default-500 m-0">请配置 OAuth 登录</p>
            )}
          </div>
        </aside>

        <main className="flex-1 min-w-0 overflow-y-auto p-4 sm:p-6 sm:px-8 pb-12 bg-default-50">
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

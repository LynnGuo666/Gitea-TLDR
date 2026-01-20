import Link from 'next/link';
import { useRouter } from 'next/router';
import { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import { DashboardIcon, UsageIcon, UserIcon, SunIcon, MoonIcon, AdminIcon } from './icons';
import {
  AuthContext,
  defaultAuthStatus,
  fetchAuthStatus,
  beginOAuthLogin,
  requestLogout,
} from '../lib/auth';
import { useTheme, useWindowFocus } from '../lib/hooks';

type LayoutProps = {
  children: ReactNode;
};

const navItems = [
  { href: '/', label: '仪表盘', icon: DashboardIcon },
  { href: '/usage', label: '用量', icon: UsageIcon },
  { href: '/settings', label: '用户中心', icon: UserIcon },
  { href: '/admin', label: '管理后台', icon: AdminIcon, adminOnly: true },
];

const AUTH_POLL_INTERVAL = 60000; // 60 seconds when window is not focused
const AUTH_POLL_INTERVAL_FOCUSED = 30000; // 30 seconds when window is focused

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();
  const [authStatus, setAuthStatus] = useState(defaultAuthStatus);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { resolvedTheme, toggleTheme } = useTheme();
  const isWindowFocused = useWindowFocus();

  const refreshAuth = useCallback(() => {
    fetchAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatus(defaultAuthStatus));
  }, []);

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  // Smart polling: more frequent when focused, less when not
  useEffect(() => {
    const interval = isWindowFocused ? AUTH_POLL_INTERVAL_FOCUSED : AUTH_POLL_INTERVAL;
    const id = setInterval(refreshAuth, interval);
    return () => clearInterval(id);
  }, [refreshAuth, isWindowFocused]);

  // Refresh on window focus
  useEffect(() => {
    if (isWindowFocused) {
      refreshAuth();
    }
  }, [isWindowFocused, refreshAuth]);

  const beginLogin = useCallback(async () => {
    try {
      await beginOAuthLogin();
    } catch (error) {
      console.error(error);
    }
  }, []);

  const logout = useCallback(async () => {
    await requestLogout();
    setShowUserMenu(false);
    refreshAuth();
  }, [refreshAuth]);

  const authContextValue = useMemo(
    () => ({
      status: authStatus,
      refresh: refreshAuth,
      beginLogin,
      logout,
    }),
    [authStatus, refreshAuth, beginLogin, logout]
  );

  const requiresLogin = authStatus.enabled && !authStatus.loggedIn;

  return (
    <AuthContext.Provider value={authContextValue}>
      <div className="app-container">
        <aside className="sidebar">
          <div className="sidebar-header">
            <div className="brand">
              <span className="brand-icon">
                <DashboardIcon size={18} />
              </span>
              <strong>Gitea PR Reviewer</strong>
            </div>
            <button
              className="theme-toggle"
              onClick={toggleTheme}
              title={resolvedTheme === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
              aria-label="切换主题"
            >
              {resolvedTheme === 'dark' ? <SunIcon size={18} /> : <MoonIcon size={18} />}
            </button>
          </div>
          <nav className="sidebar-nav">
            {navItems.map((item) => {
              // 如果是管理后台且用户未登录，跳过
              if (item.adminOnly && !authStatus.loggedIn) {
                return null;
              }
              
              const active = router.pathname === item.href || router.pathname.startsWith(item.href + '/');
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`sidebar-link ${active ? 'active' : ''}`}
                >
                  <Icon size={20} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="sidebar-footer">
            {authStatus.enabled ? (
              authStatus.loggedIn ? (
                <div className="user-profile">
                  <button
                    className="user-profile-trigger"
                    onClick={() => setShowUserMenu((prev) => !prev)}
                  >
                    {authStatus.user?.avatar_url ? (
                      <Image
                        src={authStatus.user.avatar_url}
                        alt={authStatus.user.username || 'avatar'}
                        width={32}
                        height={32}
                      />
                    ) : (
                      <span className="avatar-placeholder">
                        {(authStatus.user?.username || 'U')[0]}
                      </span>
                    )}
                    <div>
                      <strong>
                        {authStatus.user?.full_name || authStatus.user?.username || '已登录'}
                      </strong>
                      <span>@{authStatus.user?.username || ''}</span>
                    </div>
                  </button>
                  {showUserMenu && (
                    <div className="user-menu">
                      <button onClick={logout}>退出登录</button>
                    </div>
                  )}
                </div>
              ) : (
                <button className="sidebar-login" onClick={beginLogin}>
                  连接 PKUGit
                </button>
              )
            ) : (
              <p className="sidebar-hint">使用默认 PAT</p>
            )}
          </div>
        </aside>
        <main className="main-content">
          {requiresLogin ? (
            <section className="card auth-gate">
              <h1>连接 PKUGit</h1>
              <p>
                需要先授权 PKUGit 帐号后，才能加载仓库列表与审查配置。
                该授权仅用于读取你有权限的仓库，并为其创建 Webhook。
              </p>
              <button className="primary-button" onClick={beginLogin}>
                立即连接
              </button>
            </section>
          ) : (
            children
          )}
        </main>
      </div>
    </AuthContext.Provider>
  );
}

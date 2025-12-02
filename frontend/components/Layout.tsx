import Link from 'next/link';
import { useRouter } from 'next/router';
import { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { DashboardIcon, UsageIcon, UserIcon } from './icons';
import {
  AuthContext,
  defaultAuthStatus,
  fetchAuthStatus,
  beginOAuthLogin,
  requestLogout,
} from '../lib/auth';

type LayoutProps = {
  children: ReactNode;
};

const navItems = [
  { href: '/', label: '仪表盘', icon: DashboardIcon },
  { href: '/usage', label: '用量', icon: UsageIcon },
  { href: '/settings', label: '用户中心', icon: UserIcon },
];

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();
  const [authStatus, setAuthStatus] = useState(defaultAuthStatus);
  const refreshAuth = useCallback(() => {
    fetchAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatus(defaultAuthStatus));
  }, []);

  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);

  const beginLogin = useCallback(async () => {
    try {
      await beginOAuthLogin();
    } catch (error) {
      console.error(error);
    }
  }, []);

  const logout = useCallback(async () => {
    await requestLogout();
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
            <div className="sidebar-auth">
              {authStatus.enabled ? (
                authStatus.loggedIn ? (
                  <div className="user-chip">
                    <div>
                      <strong>
                        {authStatus.user?.full_name || authStatus.user?.username || '已登录'}
                      </strong>
                      <span>{authStatus.user?.username || ''}</span>
                    </div>
                    <button onClick={logout}>退出</button>
                  </div>
                ) : (
                  <button className="sidebar-login" onClick={beginLogin}>
                    连接 Gitea
                  </button>
                )
              ) : (
                <p className="sidebar-hint">使用默认 PAT</p>
              )}
            </div>
          </div>
          <nav className="sidebar-nav">
            {navItems.map((item) => {
              const active = router.pathname === item.href;
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
        </aside>
        <main className="main-content">{children}</main>
      </div>
    </AuthContext.Provider>
  );
}

import { createContext } from 'react';

export type AuthUser = {
  username?: string;
  full_name?: string;
  avatar_url?: string;
};

export type AuthStatus = {
  enabled: boolean;
  loggedIn: boolean;
  user?: AuthUser | null;
};

export type AuthContextValue = {
  status: AuthStatus;
  refresh: () => void;
  beginLogin: () => Promise<void>;
  logout: () => Promise<void>;
};

export const defaultAuthStatus: AuthStatus = {
  enabled: false,
  loggedIn: false,
  user: null,
};

export const AuthContext = createContext<AuthContextValue>({
  status: defaultAuthStatus,
  refresh: () => undefined,
  beginLogin: async () => undefined,
  logout: async () => undefined,
});

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await fetch('/api/auth/status', { credentials: 'include' });
  if (!res.ok) {
    throw new Error('无法加载登录状态');
  }
  const data = await res.json();
  return {
    enabled: Boolean(data.enabled),
    loggedIn: Boolean(data.logged_in ?? data.loggedIn),
    user: data.user,
  };
}

export async function beginOAuthLogin(): Promise<void> {
  const res = await fetch('/api/auth/login-url', { credentials: 'include' });
  if (!res.ok) {
    throw new Error('无法获取登录链接');
  }
  const data = await res.json();
  if (data?.url) {
    window.location.href = data.url;
  } else {
    throw new Error('缺少授权地址');
  }
}

export async function requestLogout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
}

import { useState, useEffect, useCallback } from 'react';
import { apiFetch, ApiError } from './api';

/**
 * Hook to persist state in localStorage with SSR support
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(initialValue);

  useEffect(() => {
    try {
      const item = window.localStorage.getItem(key);
      if (item) {
        setStoredValue(JSON.parse(item));
      }
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
    }
  }, [key]);

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      try {
        const valueToStore = value instanceof Function ? value(storedValue) : value;
        setStoredValue(valueToStore);
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
      } catch (error) {
        console.warn(`Error setting localStorage key "${key}":`, error);
      }
    },
    [key, storedValue]
  );

  return [storedValue, setValue];
}

/**
 * Hook for debounced value
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Hook to detect if window is focused
 */
export function useWindowFocus() {
  const [isFocused, setIsFocused] = useState(true);

  useEffect(() => {
    const onFocus = () => setIsFocused(true);
    const onBlur = () => setIsFocused(false);

    window.addEventListener('focus', onFocus);
    window.addEventListener('blur', onBlur);

    return () => {
      window.removeEventListener('focus', onFocus);
      window.removeEventListener('blur', onBlur);
    };
  }, []);

  return isFocused;
}

type UseApiFetchState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

/**
 * 数据获取 hook：封装 loading / error / data 三态 + apiFetch + JSON 解析 + 401 处理。
 *
 * @param url API 路径（相对 `/api/v2/...` 或完整 URL）；url 为空串时不发起请求。
 * @param options.refreshOnFocus 为 true 时窗口重新聚焦会自动刷新。
 *
 * 用法：
 *   const { data, loading, error, refresh } = useApiFetch<UsageResponse>('/api/v2/usage');
 */
export function useApiFetch<T>(url: string, options?: { refreshOnFocus?: boolean }): UseApiFetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(url));
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const isFocused = useWindowFocus();

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!url) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    apiFetch(url)
      .then(async (res) => {
        if (res.status === 401) {
          throw new ApiError('未登录或会话已过期', 401, res);
        }
        if (!res.ok) {
          throw new ApiError(`请求失败（${res.status}）`, res.status, res);
        }
        return (await res.json()) as T;
      })
      .then((json) => {
        if (active) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
        const message = err instanceof ApiError ? err.message : '加载失败，请稍后重试';
        setError(message);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [url, nonce]);

  // 窗口重新聚焦时自动刷新（可选）
  useEffect(() => {
    if (options?.refreshOnFocus && data !== null) {
      refresh();
    }
    // 仅依赖 isFocused；refresh 通过 nonce 间接触发，不纳入依赖以免循环。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFocused]);

  return { data, loading, error, refresh };
}

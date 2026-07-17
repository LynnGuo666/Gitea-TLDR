/**
 * 后端 API 调用封装。
 *
 * 默认带 `credentials: 'include'`（跨域部署也保 session cookie）。
 * 提供 `apiFetch`（返回 Response）与 `apiFetchJson`（自动 JSON 解析 + 401 处理）两层。
 */

function getApiOrigin(): string {
  return process.env.NEXT_PUBLIC_API_ORIGIN || '';
}

function isJsonResponse(res: Response): boolean {
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json');
}

/**
 * 底层 fetch 封装，返回 Response（与历史签名兼容）。
 *
 * 与裸 fetch 的区别：
 * - 默认 `credentials: 'include'`（除非 init 已显式指定），跨域部署也保 session cookie。
 */
export function apiFetch(input: string, init?: RequestInit): Promise<Response> {
  const merged: RequestInit = { credentials: 'include', ...init };
  if (input.startsWith('http://') || input.startsWith('https://')) {
    return fetch(input, merged);
  }

  const origin = getApiOrigin();
  const url = origin ? `${origin}${input}` : input;

  return fetch(url, merged);
}

type Json = Record<string, unknown> | unknown[] | string | number | boolean | null;

/**
 * JSON 版 API 调用：自动解析 JSON，非 2xx 抛错（错误信息取 detail/message）。
 *
 * @param input API 路径（相对 `/api/v2/...`）或完整 URL
 * @param init fetch init（有 body 时自动加 Content-Type: application/json）
 * @returns 解析后的 JSON（泛型 T 由调用方指定）
 */
export async function apiFetchJson<T = Json>(input: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await apiFetch(input, { ...init, headers });

  if (res.status === 401) {
    throw new ApiError('未登录或会话已过期', 401, res);
  }
  if (!res.ok) {
    const fallback = `请求失败（${res.status}）`;
    let message = fallback;
    if (isJsonResponse(res)) {
      try {
        const data = (await res.json()) as { detail?: unknown; message?: unknown };
        const detail = data.detail ?? data.message;
        if (typeof detail === 'string' && detail.trim()) message = detail;
      } catch {
        // 响应体不是合法 JSON，使用 fallback
      }
    }
    throw new ApiError(message, res.status, res);
  }

  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return (await res.json()) as T;
}

/** API 调用错误，携带 HTTP 状态码。 */
export class ApiError extends Error {
  status: number;
  response: Response;

  constructor(message: string, status: number, response: Response) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.response = response;
  }
}

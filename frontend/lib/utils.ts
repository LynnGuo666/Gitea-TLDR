import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** 相对时间格式化（"3 分钟前" / "2 小时前" / "5 天前"）。 */
export function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

/** 读取后端错误响应中的 detail/message，失败时返回 fallback。 */
export async function readErrorMessage(res: Response, fallback: string): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown; message?: unknown };
    const detail = data.detail ?? data.message;
    if (typeof detail === 'string' && detail.trim()) return detail;
  } catch {
    // Response body is not JSON.
  }
  return fallback;
}

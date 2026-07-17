import { ReactNode } from 'react';

type ErrorStateProps = {
  message?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
};

/** 错误状态占位：加载失败时统一展示，提供重试入口。 */
export default function ErrorState({
  message = '加载失败',
  description = '请检查网络或稍后重试',
  action,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 rounded-xl border border-danger/40 bg-danger/5 py-10 px-6 text-center ${className || ''}`.trim()}
    >
      <p className="m-0 text-sm font-medium text-danger">{message}</p>
      {description ? <p className="m-0 text-xs text-default-500 max-w-md">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

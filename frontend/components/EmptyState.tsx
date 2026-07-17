import { ReactNode } from 'react';

type EmptyStateProps = {
  title?: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
};

/** 空状态占位：列表/数据为空时统一展示，与 PageHeader/SectionHeader 风格一致。 */
export default function EmptyState({
  title = '暂无数据',
  description,
  icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 rounded-xl border border-divider/60 bg-content1/40 py-12 px-6 text-center ${className || ''}`.trim()}
    >
      {icon ? <div className="text-default-400">{icon}</div> : null}
      <p className="m-0 text-sm font-medium text-default-600">{title}</p>
      {description ? <p className="m-0 text-xs text-default-400 max-w-md">{description}</p> : null}
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}

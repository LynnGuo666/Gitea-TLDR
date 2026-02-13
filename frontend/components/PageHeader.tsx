import { ReactNode } from 'react';

type PageHeaderProps = {
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export default function PageHeader({ title, subtitle, icon, actions, className }: PageHeaderProps) {
  return (
    <div className={`flex items-start justify-between gap-3 flex-wrap ${className || ''}`.trim()}>
      <div className="flex items-start gap-2.5 min-w-0">
        {icon ? (
          <span className="mt-0.5 w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center shrink-0">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <h1 className="m-0 page-title truncate">{title}</h1>
          {subtitle ? <p className="m-0 mt-2 text-sm text-default-500">{subtitle}</p> : null}
        </div>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

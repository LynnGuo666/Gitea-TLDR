import { ReactNode } from 'react';

type SectionHeaderProps = {
  title: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
};

export default function SectionHeader({ title, icon, actions, className }: SectionHeaderProps) {
  return (
    <div className={`flex items-center justify-between gap-3 flex-wrap ${className || ''}`.trim()}>
      <div className="flex items-center gap-2.5 min-w-0">
        {icon ? (
          <span className="w-8 h-8 rounded-lg border border-default-300 flex items-center justify-center shrink-0">
            {icon}
          </span>
        ) : null}
        <h2 className="m-0 text-xl font-bold tracking-tight truncate">{title}</h2>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

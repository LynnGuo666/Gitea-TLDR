import Link from 'next/link';
import { useRouter } from 'next/router';
import { ReactNode } from 'react';
import { DashboardIcon, UsageIcon, UserIcon } from './icons';

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

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <span className="brand-icon">
              <DashboardIcon size={18} />
            </span>
            <strong>Gitea PR Reviewer</strong>
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
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

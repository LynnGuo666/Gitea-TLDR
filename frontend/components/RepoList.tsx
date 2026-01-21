import Link from 'next/link';
import { Repo } from '../lib/types';
import { RepoIcon } from './icons';

type RepoListProps = {
  repos: Repo[];
};

export default function RepoList({ repos }: RepoListProps) {
  if (repos.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">
          <RepoIcon size={32} />
        </div>
        <h3>暂无仓库</h3>
        <p>还没有找到任何仓库</p>
      </div>
    );
  }

  return (
    <div className="repo-list">
      {repos.map((repo, index) => {
        const owner = repo.owner?.username || repo.owner?.login || '未知';
        const fullName = repo.full_name || `${owner}/${repo.name}`;
        const isActive = repo.is_active ?? false;
        const isReadOnly = !repo.permissions?.admin;

        const itemStyle = {
          animationDelay: `${index * 40}ms`,
          animationName: 'repoFadeUp',
          animationDuration: '0.35s',
          animationFillMode: 'both' as const,
          cursor: isReadOnly ? 'default' : 'pointer',
        };

        const content = (
          <>
            <div className="repo-item-icon">
              <RepoIcon size={20} />
            </div>
            <div className="repo-item-content">
              <div className="repo-item-header">
                <h3 className="repo-item-name">{fullName}</h3>
                <div className="repo-item-badges">
                  {repo.private && <span className="repo-badge repo-badge-private">私有</span>}
                  {isReadOnly ? (
                    <span className="repo-badge repo-badge-readonly">只读</span>
                  ) : (
                    <span className={`repo-badge ${isActive ? 'repo-badge-active' : 'repo-badge-inactive'}`}>
                      {isActive ? '已启用' : '未启用'}
                    </span>
                  )}
                </div>
              </div>
            </div>
            {isReadOnly ? null : (
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="repo-item-arrow"
              >
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            )}
          </>
        );

        if (isReadOnly) {
          return (
            <div key={repo.id} className="repo-item" style={itemStyle}>
              {content}
            </div>
          );
        }

        return (
          <Link key={repo.id} href={`/repo/${owner}/${repo.name}`} className="repo-item" style={itemStyle}>
            {content}
          </Link>
        );
      })}
    </div>
  );
}

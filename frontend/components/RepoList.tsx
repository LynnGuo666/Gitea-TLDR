import Link from 'next/link';
import { Repo } from '../lib/types';
import { ChevronRightIcon, RepoIcon } from './icons';

type RepoListProps = {
  repos: Repo[];
};

export default function RepoList({ repos }: RepoListProps) {
  if (repos.length === 0) {
    return (
      <div className="empty-state">
        <RepoIcon size={48} />
        <p>暂无仓库</p>
      </div>
    );
  }

  return (
    <div className="repo-list">
      {repos.map((repo, index) => {
        const owner = repo.owner?.username || repo.owner?.login || '未知';
        const fullName = repo.full_name || `${owner}/${repo.name}`;
        const visibility = repo.private ? '私有' : '公开';
        return (
          <Link
            key={repo.id}
            href={`/repo/${repo.owner?.username || repo.owner?.login}/${repo.name}`}
            className="repo-item"
            style={{ animationDelay: `${index * 60}ms` }}
          >
            <div className="repo-item-icon">
              <RepoIcon size={20} />
            </div>
            <div className="repo-item-content">
              <h3>{fullName}</h3>
              <p>
                <span className="repo-meta-pill">{visibility}</span>
                <span>{owner}</span>
              </p>
            </div>
            <ChevronRightIcon size={20} className="repo-item-arrow" />
          </Link>
        );
      })}
    </div>
  );
}

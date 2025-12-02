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
      {repos.map((repo) => {
        const fullName = repo.full_name || `${repo.owner?.username || repo.owner?.login}/${repo.name}`;
        return (
          <Link
            key={repo.id}
            href={`/repo/${repo.owner?.username || repo.owner?.login}/${repo.name}`}
            className="repo-item"
          >
            <div className="repo-item-icon">
              <RepoIcon size={20} />
            </div>
            <div className="repo-item-content">
              <h3>{fullName}</h3>
              {repo.private && <span className="badge-private">私有</span>}
            </div>
            <ChevronRightIcon size={20} className="repo-item-arrow" />
          </Link>
        );
      })}
    </div>
  );
}

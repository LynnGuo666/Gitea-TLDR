import Link from 'next/link';
import { memo } from 'react';
import { Chip } from '@heroui/react';
import { FolderGit2, ChevronRight } from 'lucide-react';
import { Repo } from '../lib/types';

type RepoListProps = {
  repos: Repo[];
};

function RepoList({ repos }: RepoListProps) {
  if (repos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-default-500 gap-4">
        <div className="w-16 h-16 rounded-xl bg-default-100 flex items-center justify-center text-default-400">
          <FolderGit2 size={32} />
        </div>
        <h3 className="m-0 text-foreground text-base">暂无仓库</h3>
        <p className="m-0 text-sm">还没有找到任何仓库</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
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
        };

        const itemClassName = `group flex items-center gap-4 p-4 sm:p-5 bg-content1 rounded-xl no-underline text-foreground shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5 ${
          isReadOnly ? 'cursor-default' : 'cursor-pointer'
        }`;

        const content = (
          <>
            <div className="w-10 h-10 rounded-lg bg-default-100 flex items-center justify-center text-default-500 shrink-0 group-hover:bg-primary-100 group-hover:text-primary transition-colors">
              <FolderGit2 size={20} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-4 flex-wrap mb-1">
                <h3 className="m-0 text-sm font-semibold text-foreground truncate">{fullName}</h3>
                <div className="flex items-center gap-1 flex-wrap">
                  {repo.private && (
                    <Chip size="sm" variant="bordered">私有</Chip>
                  )}
                  {isReadOnly ? (
                    <Chip size="sm" variant="flat" color="default">只读</Chip>
                  ) : (
                    <Chip size="sm" variant="flat" color={isActive ? 'success' : 'danger'}>
                      {isActive ? '已启用' : '未启用'}
                    </Chip>
                  )}
                </div>
              </div>
            </div>
            {!isReadOnly && (
              <ChevronRight
                size={20}
                className="text-default-400 shrink-0 transition-transform group-hover:text-primary group-hover:translate-x-1"
              />
            )}
          </>
        );

        if (isReadOnly) {
          return (
            <div key={repo.id} className={itemClassName} style={itemStyle}>
              {content}
            </div>
          );
        }

        return (
          <Link key={repo.id} href={`/repo/${owner}/${repo.name}`} className={itemClassName} style={itemStyle}>
            {content}
          </Link>
        );
      })}
    </div>
  );
}

export default memo(RepoList);

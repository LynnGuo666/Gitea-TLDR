import { Repo } from '../lib/types';
import { FolderGit2, Lock, ChevronRight } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table';
import { Badge } from './ui/badge';

type RepoListProps = {
  repos: Repo[];
};

export default function RepoList({ repos }: RepoListProps) {
  if (repos.length === 0) {
    return (
      <div className="empty-state">
        <FolderGit2 size={48} />
        <p>暂无仓库</p>
      </div>
    );
  }

  return (
    <div className="repo-table-container">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>仓库名称</TableHead>
            <TableHead>可见性</TableHead>
            <TableHead>所有者</TableHead>
            <TableHead>状态</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {repos.map((repo, index) => {
            const owner = repo.owner?.username || repo.owner?.login || '未知';
            const fullName = repo.full_name || `${owner}/${repo.name}`;
            const visibility = repo.private ? '私有' : '公开';
            const isActive = repo.is_active ?? true;
            const isReadOnly = !repo.permissions?.admin;

            return (
              <TableRow
                key={repo.id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                style={{ animationDelay: `${index * 60}ms` }}
                onClick={() => window.location.href = `/repo/${owner}/${repo.name}`}
              >
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    <FolderGit2 size={18} className="text-muted-foreground" />
                    <span>{fullName}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={repo.private ? 'secondary' : 'outline'}>
                    {visibility}
                  </Badge>
                </TableCell>
                <TableCell>{owner}</TableCell>
                <TableCell>
                  {isReadOnly ? (
                    <Badge variant="secondary" className="gap-1">
                      <Lock size={12} />
                      只读
                    </Badge>
                  ) : (
                    <Badge variant={isActive ? 'default' : 'destructive'}>
                      {isActive ? '已启用' : '未启用'}
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  <ChevronRight size={18} className="text-muted-foreground" />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

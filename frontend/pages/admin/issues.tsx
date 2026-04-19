import Head from 'next/head';
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Chip,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from '@heroui/react';
import { CheckCircle2, Clock, Lightbulb, RefreshCw, XCircle } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';
import { IssueAnalysisDetail, IssueAnalysisItem } from '../../lib/types';

type IssueListResponse = {
  issues: IssueAnalysisItem[];
  total: number;
  limit: number;
  offset: number;
};

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function renderStatus(success: boolean | null) {
  if (success === true) return <Chip color="success" variant="flat" size="sm" startContent={<CheckCircle2 size={14} />}>成功</Chip>;
  if (success === false) return <Chip color="danger" variant="flat" size="sm" startContent={<XCircle size={14} />}>失败</Chip>;
  return <Chip color="default" variant="flat" size="sm" startContent={<Clock size={14} />}>进行中</Chip>;
}

export default function AdminIssuesPage() {
  const [issues, setIssues] = useState<IssueAnalysisItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, IssueAnalysisDetail>>({});
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null);

  const fetchIssues = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/issues?limit=50&offset=0');
      if (!res.ok) throw new Error('获取 Issue 分析记录失败');
      const data = (await res.json()) as IssueListResponse;
      setIssues(data.issues);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取 Issue 分析记录失败');
      setIssues([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchIssues();
  }, [fetchIssues]);

  const loadDetail = useCallback(async (id: number) => {
    if (detailCache[id]) return;
    setDetailLoadingId(id);
    try {
      const res = await apiFetch(`/api/issues/${id}`);
      if (!res.ok) throw new Error('获取详情失败');
      const detail = (await res.json()) as IssueAnalysisDetail;
      setDetailCache((prev) => ({ ...prev, [id]: detail }));
    } catch {
      // noop
    } finally {
      setDetailLoadingId(null);
    }
  }, [detailCache]);

  const handleRowClick = (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    void loadDetail(id);
  };

  const renderExpanded = (id: number) => {
    if (detailLoadingId === id && !detailCache[id]) {
      return (
        <div className="flex justify-center p-8">
          <Spinner size="lg" />
        </div>
      );
    }
    const detail = detailCache[id];
    if (!detail) return <div className="p-4 text-danger">无法加载详情</div>;

    return (
      <div className="rounded-lg bg-content2/50 p-4 text-sm flex flex-col gap-4">
        <div className="rounded-lg border border-default-200 bg-content1 p-3 whitespace-pre-wrap">
          {detail.summary_markdown || '—'}
        </div>
        <div>
          <p className="m-0 mb-2 font-medium">相似 Issue ({detail.related_issues.length})</p>
          {detail.related_issues.length === 0 ? (
            <p className="m-0 text-default-500">暂无</p>
          ) : (
            <div className="flex flex-col gap-2">
              {detail.related_issues.map((item) => (
                <div key={`${id}-${item.number}`} className="rounded border border-default-200 bg-content1 p-3">
                  <p className="m-0 font-medium">#{item.number} {item.title}</p>
                  <p className="m-0 mt-1 text-default-600">{item.similarity_reason}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div>
          <p className="m-0 mb-2 font-medium">解决方案 ({detail.solution_suggestions.length})</p>
          {detail.solution_suggestions.length === 0 ? (
            <p className="m-0 text-default-500">暂无</p>
          ) : (
            <div className="flex flex-col gap-2">
              {detail.solution_suggestions.map((item, index) => (
                <div key={`${id}-${index}`} className="rounded border border-default-200 bg-content1 p-3">
                  <p className="m-0 font-medium">{item.title}</p>
                  <p className="m-0 mt-1 text-default-600">{item.summary}</p>
                </div>
              ))}
            </div>
          )}
        </div>
        {detail.error_message ? (
          <div className="rounded-lg border border-danger bg-danger-50 p-3 text-danger">
            {detail.error_message}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <>
      <Head>
        <title>管理后台 - Issue 分析</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="Issue 分析记录"
          icon={<Lightbulb size={20} />}
          actions={
            <Button isIconOnly variant="bordered" size="sm" onPress={() => fetchIssues()} isDisabled={loading} aria-label="刷新 Issue 分析记录">
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </Button>
          }
        />

        {error ? (
          <div className="rounded-lg border border-danger bg-danger-50 p-4 text-danger">{error}</div>
        ) : loading ? (
          <div className="py-10 text-center text-default-500">加载中...</div>
        ) : issues.length === 0 ? (
          <div className="py-10 text-center text-default-500">暂无 Issue 分析记录</div>
        ) : (
          <Table aria-label="Issue 分析记录">
            <TableHeader>
              <TableColumn>仓库</TableColumn>
              <TableColumn>Issue</TableColumn>
              <TableColumn>触发方式</TableColumn>
              <TableColumn>模型</TableColumn>
              <TableColumn>关联数</TableColumn>
              <TableColumn>方案数</TableColumn>
              <TableColumn>状态</TableColumn>
              <TableColumn>开始时间</TableColumn>
            </TableHeader>
            <TableBody>
              {issues.flatMap((issue) => {
                const isExpanded = expandedId === issue.id;
                return [
                  <TableRow key={issue.id} onClick={() => handleRowClick(issue.id)} className="cursor-pointer">
                    <TableCell>{issue.repo_full_name || `#${issue.repository_id}`}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-primary text-xs">#{issue.issue_number}</span>
                        <span className="text-xs text-default-500 truncate max-w-[240px]">{issue.issue_title || '-'}</span>
                      </div>
                    </TableCell>
                    <TableCell>{issue.trigger_type}</TableCell>
                    <TableCell>{issue.model || issue.engine || '—'}</TableCell>
                    <TableCell>{issue.related_issue_count}</TableCell>
                    <TableCell>{issue.solution_count}</TableCell>
                    <TableCell>{renderStatus(issue.overall_success)}</TableCell>
                    <TableCell>{formatTime(issue.started_at)}</TableCell>
                  </TableRow>,
                  ...(isExpanded ? [
                    <TableRow key={`${issue.id}-detail`}>
                      <TableCell colSpan={8}>{renderExpanded(issue.id)}</TableCell>
                    </TableRow>,
                  ] : []),
                ];
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </>
  );
}

import Head from 'next/head';
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Chip,
  Code,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from '@heroui/react';
import { CheckCircle2, Clock, Lightbulb, RefreshCw, XCircle } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { apiFetch } from '../lib/api';
import { IssueAnalysisDetail, IssueAnalysisItem } from '../lib/types';

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

function formatTokens(value: number | null | undefined): string {
  if (!value) return '—';
  return new Intl.NumberFormat('zh-CN').format(value);
}

function renderStatus(success: boolean | null) {
  if (success === true) {
    return (
      <Chip color="success" variant="flat" size="sm" startContent={<CheckCircle2 size={14} />}>
        成功
      </Chip>
    );
  }
  if (success === false) {
    return (
      <Chip color="danger" variant="flat" size="sm" startContent={<XCircle size={14} />}>
        失败
      </Chip>
    );
  }
  return (
    <Chip color="default" variant="flat" size="sm" startContent={<Clock size={14} />}>
      进行中
    </Chip>
  );
}

export default function IssuesPage() {
  const [issues, setIssues] = useState<IssueAnalysisItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, IssueAnalysisDetail>>({});
  const [loadingDetailId, setLoadingDetailId] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchIssues = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/my/issues?limit=50&offset=0');
      if (!res.ok) {
        throw new Error('获取 Issue 分析记录失败');
      }
      const data = (await res.json()) as IssueListResponse;
      setIssues(data.issues);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取 Issue 分析记录失败');
      setIssues([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchIssues();
  }, [fetchIssues]);

  const fetchDetail = useCallback(async (id: number) => {
    setLoadingDetailId(id);
    try {
      const res = await apiFetch(`/api/my/issues/${id}`);
      if (!res.ok) {
        throw new Error('获取详情失败');
      }
      const detail = (await res.json()) as IssueAnalysisDetail;
      setDetailCache((prev) => ({ ...prev, [id]: detail }));
    } catch {
      // noop
    } finally {
      setLoadingDetailId(null);
    }
  }, []);

  const toggleExpand = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!detailCache[id]) {
      await fetchDetail(id);
    }
  };

  const renderExpanded = (id: number) => {
    if (loadingDetailId === id && !detailCache[id]) {
      return (
        <div className="flex justify-center p-8">
          <Spinner size="lg" />
        </div>
      );
    }

    const detail = detailCache[id];
    if (!detail) {
      return <div className="p-4 text-danger">无法加载详情</div>;
    }

    return (
      <div className="rounded-lg bg-content2/50 p-4 text-sm flex flex-col gap-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 rounded-md border border-default-200 bg-content1 p-3">
          <div>
            <span className="block text-xs text-default-500 mb-1">模型</span>
            <Code size="sm">{detail.model || '—'}</Code>
          </div>
          <div>
            <span className="block text-xs text-default-500 mb-1">触发方式</span>
            <span>{detail.trigger_type}</span>
          </div>
          <div>
            <span className="block text-xs text-default-500 mb-1">关联 Issue</span>
            <span>{detail.related_issue_count}</span>
          </div>
          <div>
            <span className="block text-xs text-default-500 mb-1">方案数</span>
            <span>{detail.solution_count}</span>
          </div>
        </div>

        <div>
          <p className="m-0 mb-2 text-sm font-medium">摘要</p>
          <div className="rounded-lg border border-default-200 bg-content1 p-3 whitespace-pre-wrap">
            {detail.summary_markdown || '—'}
          </div>
        </div>

        <div>
          <p className="m-0 mb-2 text-sm font-medium">相似 Issue</p>
          {detail.related_issues.length === 0 ? (
            <p className="m-0 text-default-500">暂无关联 Issue</p>
          ) : (
            <div className="flex flex-col gap-3">
              {detail.related_issues.map((item) => (
                <div key={`${detail.id}-${item.number}`} className="rounded-lg border border-default-200 bg-content1 p-3">
                  <p className="m-0 font-medium">#{item.number} {item.title}</p>
                  <p className="m-0 mt-1 text-default-500">状态: {item.state}</p>
                  <p className="m-0 mt-1">{item.similarity_reason}</p>
                  <p className="m-0 mt-1 text-default-600">参考点: {item.suggested_reference}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="m-0 mb-2 text-sm font-medium">解决方案</p>
          {detail.solution_suggestions.length === 0 ? (
            <p className="m-0 text-default-500">暂无解决方案</p>
          ) : (
            <div className="flex flex-col gap-3">
              {detail.solution_suggestions.map((item, index) => (
                <div key={`${detail.id}-${index}`} className="rounded-lg border border-default-200 bg-content1 p-3">
                  <p className="m-0 font-medium">{index + 1}. {item.title}</p>
                  <p className="m-0 mt-1 text-default-600">{item.summary}</p>
                  <div className="mt-2 flex flex-col gap-1">
                    {item.steps.map((step, stepIndex) => (
                      <p key={`${detail.id}-${index}-${stepIndex}`} className="m-0 text-sm">
                        {stepIndex + 1}. {step}
                      </p>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <p className="m-0 mb-2 text-sm font-medium">相关文件</p>
            {detail.related_files.length === 0 ? (
              <p className="m-0 text-default-500">暂无</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {detail.related_files.map((file) => (
                  <Chip key={file} size="sm" variant="flat">{file}</Chip>
                ))}
              </div>
            )}
          </div>
          <div>
            <p className="m-0 mb-2 text-sm font-medium">推荐下一步</p>
            {detail.next_actions.length === 0 ? (
              <p className="m-0 text-default-500">暂无</p>
            ) : (
              <div className="flex flex-col gap-1">
                {detail.next_actions.map((action, index) => (
                  <p key={`${detail.id}-action-${index}`} className="m-0">{index + 1}. {action}</p>
                ))}
              </div>
            )}
          </div>
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
        <title>Issue 分析 - LCPU AI Reviewer</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="Issue 分析"
          icon={<Lightbulb size={20} />}
          actions={
            <Button
              isIconOnly
              variant="bordered"
              size="sm"
              onPress={() => fetchIssues(true)}
              isDisabled={refreshing}
              aria-label="刷新 Issue 分析记录"
            >
              <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            </Button>
          }
        />

        {loading ? (
          <div className="py-10 text-center text-default-500">加载中...</div>
        ) : error ? (
          <div className="rounded-lg border border-danger bg-danger-50 p-4 text-danger">
            {error}
          </div>
        ) : issues.length === 0 ? (
          <div className="py-10 text-center text-default-500">暂无 Issue 分析记录</div>
        ) : (
          <Table aria-label="Issue 分析记录">
            <TableHeader>
              <TableColumn>仓库</TableColumn>
              <TableColumn>Issue</TableColumn>
              <TableColumn>触发方式</TableColumn>
              <TableColumn>模型</TableColumn>
              <TableColumn>关联</TableColumn>
              <TableColumn>方案</TableColumn>
              <TableColumn>状态</TableColumn>
              <TableColumn>Tokens</TableColumn>
              <TableColumn>开始时间</TableColumn>
            </TableHeader>
            <TableBody>
              {issues.flatMap((item) => {
                const isExpanded = expandedId === item.id;
                return [
                  <TableRow key={item.id} onClick={() => void toggleExpand(item.id)} className="cursor-pointer">
                    <TableCell>{item.repo_full_name || `#${item.repository_id}`}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="text-primary text-xs">#{item.issue_number}</span>
                        <span className="text-xs text-default-500 truncate max-w-[240px]">{item.issue_title || '-'}</span>
                      </div>
                    </TableCell>
                    <TableCell>{item.trigger_type}</TableCell>
                    <TableCell>{item.model || item.engine || '—'}</TableCell>
                    <TableCell>{item.related_issue_count}</TableCell>
                    <TableCell>{item.solution_count}</TableCell>
                    <TableCell>{renderStatus(item.overall_success)}</TableCell>
                    <TableCell>{formatTokens(item.total_tokens)}</TableCell>
                    <TableCell>{formatTime(item.started_at)}</TableCell>
                  </TableRow>,
                  ...(isExpanded
                    ? [
                        <TableRow key={`${item.id}-detail`}>
                          <TableCell colSpan={9}>{renderExpanded(item.id)}</TableCell>
                        </TableRow>,
                      ]
                    : []),
                ];
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </>
  );
}

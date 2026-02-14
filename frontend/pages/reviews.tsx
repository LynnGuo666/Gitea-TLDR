import Head from 'next/head';
import { useEffect, useState, useCallback } from 'react';
import {
  Button, Table, TableHeader, TableColumn, TableBody, TableRow, TableCell,
  Chip, Select, SelectItem, Spinner, Code
} from '@heroui/react';
import { RefreshCw, ChevronDown, ChevronUp, AlertCircle, CheckCircle2, XCircle, Clock, BookOpen, Timer } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { apiFetch } from '../lib/api';

type ReviewItem = {
  id: number;
  repository_id: number;
  repo_full_name: string | null;
  pr_number: number;
  pr_title: string | null;
  pr_author: string | null;
  trigger_type: string;
  analysis_mode: string | null;
  provider_name: string | null;
  model_name: string | null;
  config_source: string | null;
  overall_severity: string | null;
  overall_success: boolean | null;
  inline_comments_count: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
};

type ReviewDetail = ReviewItem & {
  enabled_features: string[];
  focus_areas: string[];
  summary_markdown: string | null;
  error_message: string | null;
  head_branch: string | null;
  base_branch: string | null;
  head_sha: string | null;
  diff_size_bytes: number | null;
  inline_comments: InlineComment[];
};

type InlineComment = {
  id: number;
  file_path: string;
  new_line: number | null;
  old_line: number | null;
  severity: string | null;
  comment: string;
  suggestion: string | null;
};

type ReviewsResponse = {
  reviews: ReviewItem[];
  total: number;
  limit: number;
  offset: number;
};

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function renderFocusChips(focusAreas: string[] | null | undefined) {
  if (!focusAreas || focusAreas.length === 0) return <span className="text-default-400">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {focusAreas.map((focus) => (
        <Chip key={focus} size="sm" variant="flat" className="h-5 text-[10px]">
          {focus}
        </Chip>
      ))}
    </div>
  );
}

export default function ReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all'); // all, success, fail
  
  // Expansion state
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailsCache, setDetailsCache] = useState<Record<number, ReviewDetail>>({});
  const [loadingDetailId, setLoadingDetailId] = useState<number | null>(null);

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = '/api/my/reviews?limit=50&offset=0';
      if (filter === 'success') url += '&success=true';
      if (filter === 'fail') url += '&success=false';
      
      const res = await apiFetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch: ${res.statusText}`);
      }
      const data = await res.json() as ReviewsResponse;
      setReviews(data.reviews);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取审查记录失败');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const toggleExpand = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(id);
    
    if (detailsCache[id]) return;

    setLoadingDetailId(id);
    try {
      const res = await apiFetch(`/api/reviews/${id}`);
      if (!res.ok) {
        throw new Error('Failed to fetch detail');
      }
      const detail = await res.json() as ReviewDetail;
      setDetailsCache(prev => ({ ...prev, [id]: detail }));
    } catch (err) {
      console.error('Failed to fetch review detail', err);
    } finally {
      setLoadingDetailId(null);
    }
  };

  const renderStatus = (success: boolean | null) => {
    if (success === true) return <Chip color="success" variant="flat" size="sm" startContent={<CheckCircle2 size={14} />}>成功</Chip>;
    if (success === false) return <Chip color="danger" variant="flat" size="sm" startContent={<XCircle size={14} />}>失败</Chip>;
    return <Chip color="default" variant="flat" size="sm" startContent={<Clock size={14} />}>进行中</Chip>;
  };

  const renderDetailContent = (id: number) => {
    const detail = detailsCache[id];
    const isLoading = loadingDetailId === id;

    if (isLoading) {
      return (
        <div className="flex justify-center p-8">
          <Spinner size="lg" />
        </div>
      );
    }

    if (!detail) {
      return <div className="p-4 text-danger">无法加载详情</div>;
    }

    return (
      <div className="p-4 bg-content2/50 rounded-lg flex flex-col gap-4 text-sm">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 p-3 bg-content1 rounded-md border border-default-200">
          <div>
            <span className="text-default-500 block text-xs mb-1">Commit</span>
            <Code size="sm">{detail.head_sha?.substring(0, 7) || '—'}</Code>
          </div>
          <div>
            <span className="text-default-500 block text-xs mb-1">调用模型</span>
            <Code size="sm">{detail.model_name || detail.provider_name || '—'}</Code>
          </div>
          <div>
            <span className="text-default-500 block text-xs mb-1">变更大小</span>
            <span className="font-mono text-default-700">
              {detail.diff_size_bytes ? `${Math.round(detail.diff_size_bytes / 1024)} KB` : '—'}
            </span>
          </div>
          <div>
            <span className="text-default-500 block text-xs mb-1">评论数</span>
            <span className="font-mono text-default-700">{detail.inline_comments_count}</span>
          </div>
        </div>

        <div>
          <span className="text-default-500 block text-xs mb-2">审查方向</span>
          {renderFocusChips(detail.focus_areas)}
        </div>

        {detail.error_message && (
          <div className="p-3 bg-danger-50 text-danger-600 border border-danger-200 rounded-md flex items-start gap-2">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <div className="whitespace-pre-wrap font-mono text-xs">{detail.error_message}</div>
          </div>
        )}

        {detail.summary_markdown && (
          <div className="flex flex-col gap-2">
            <h3 className="font-semibold text-foreground">审查摘要</h3>
            <div className="p-3 bg-content1 rounded-md border border-default-200 whitespace-pre-wrap font-mono text-xs overflow-x-auto max-h-60">
              {detail.summary_markdown}
            </div>
          </div>
        )}

        {detail.inline_comments && detail.inline_comments.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="font-semibold text-foreground">代码建议 ({detail.inline_comments.length})</h3>
            <div className="flex flex-col gap-2">
              {detail.inline_comments.map((comment) => (
                <div key={comment.id} className="p-3 bg-content1 rounded-md border border-default-200 flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Code size="sm" color="primary">{comment.file_path}</Code>
                      <span className="text-xs text-default-500">Lines {comment.new_line || comment.old_line}</span>
                    </div>
                    {comment.severity && (
                      <Chip size="sm" variant="flat" color={comment.severity === 'high' ? 'danger' : 'warning'}>
                        {comment.severity}
                      </Chip>
                    )}
                  </div>
                  <div className="text-default-700">{comment.comment}</div>
                  {comment.suggestion && (
                    <div className="bg-default-100 p-2 rounded border border-default-200 overflow-x-auto">
                      <pre className="text-xs m-0">{comment.suggestion}</pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      <Head>
        <title>审查记录 - Gitea PR Reviewer</title>
      </Head>

      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader 
          title="审查记录" 
          subtitle="查看您有权限的仓库的 PR 审查历史"
          actions={
            <div className="flex items-center gap-2">
              <Select 
                labelPlacement="outside" 
                placeholder="筛选状态" 
                selectedKeys={[filter]} 
                className="w-32" 
                size="sm"
                disallowEmptySelection
                onChange={(e) => setFilter(e.target.value)}
              >
                <SelectItem key="all" textValue="全部">全部</SelectItem>
                <SelectItem key="success" textValue="成功">成功</SelectItem>
                <SelectItem key="fail" textValue="失败">失败</SelectItem>
              </Select>
              <Button 
                isIconOnly 
                variant="flat" 
                onPress={fetchReviews}
                isLoading={loading}
              >
                <RefreshCw size={18} />
              </Button>
            </div>
          }
        />

        {loading && reviews.length === 0 ? (
          <div className="flex flex-col gap-4">
            <div className="h-12 w-full rounded-lg bg-default-100 animate-pulse" />
            <div className="h-64 w-full rounded-lg bg-default-50 animate-pulse border border-default-200" />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 text-default-500 gap-4 bg-content1 rounded-lg border border-danger-200">
            <AlertCircle size={48} className="text-danger-400" />
            <p className="m-0 text-danger-600 font-medium">{error}</p>
            <Button color="primary" variant="flat" onPress={fetchReviews}>重试</Button>
          </div>
        ) : reviews.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-default-400 gap-4 bg-content1 rounded-lg border border-dashed border-default-300">
            <BookOpen size={48} className="opacity-50" />
            <p className="m-0 text-lg">暂无审查记录</p>
            <p className="text-sm opacity-70 max-w-md text-center">
              当您有权限的仓库触发 PR 审查时，记录将显示在这里。
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-default-200 overflow-hidden bg-content1">
            <Table 
              aria-label="Review history table" 
              removeWrapper 
              isStriped
              className="min-w-full"
            >
              <TableHeader>
                <TableColumn>仓库</TableColumn>
                <TableColumn>PR</TableColumn>
                <TableColumn>触发</TableColumn>
                <TableColumn>引擎</TableColumn>
                <TableColumn>耗时</TableColumn>
                <TableColumn>状态</TableColumn>
                <TableColumn>时间</TableColumn>
                <TableColumn width={50}> </TableColumn>
              </TableHeader>
              <TableBody>
                {reviews.flatMap((review) => {
                  const isExpanded = expandedId === review.id;
                  
                  // Main row
                  const mainRow = (
                    <TableRow key={`row-${review.id}`} className="cursor-pointer hover:bg-default-100/50 transition-colors" onClick={() => toggleExpand(review.id)}>
                      <TableCell>
                        <div className="font-medium text-foreground">{review.repo_full_name}</div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-mono text-xs text-primary">#{review.pr_number}</span>
                          <span className="text-tiny text-default-500 truncate max-w-[180px]" title={review.pr_title || ''}>
                            {review.pr_title || 'No Title'}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Chip size="sm" variant="dot" color={review.trigger_type === 'webhook' ? 'primary' : 'secondary'}>
                          {review.trigger_type === 'webhook' ? 'Webhook' : 'Comment'}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="text-small text-default-700">{review.provider_name || '—'}</span>
                          <span className="text-tiny text-default-500">{review.model_name || '—'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-default-500">
                          <Timer size={14} />
                          <span className="font-mono">{formatDuration(review.duration_seconds)}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {renderStatus(review.overall_success)}
                      </TableCell>
                      <TableCell>
                        <div className="text-small text-default-500 whitespace-nowrap">
                          {formatTime(review.started_at)}
                        </div>
                      </TableCell>
                      <TableCell>
                        {isExpanded ? <ChevronUp size={18} className="text-default-400" /> : <ChevronDown size={18} className="text-default-400" />}
                      </TableCell>
                    </TableRow>
                  );

                  // Detail row (conditionally rendered)
                  if (!isExpanded) return [mainRow];

                  const detailRow = (
                    <TableRow key={`detail-${review.id}`} className="hover:none">
                      <TableCell colSpan={8} className="p-0 border-t border-dashed border-default-200 bg-content2/30">
                        {renderDetailContent(review.id)}
                      </TableCell>
                    </TableRow>
                  );

                  return [mainRow, detailRow];
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </>
  );
}

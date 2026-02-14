import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  Button,
  Chip,
  Pagination,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from '@heroui/react';
import { ArrowLeft, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';

type InlineComment = {
  id: number;
  file_path: string;
  new_line: number | null;
  old_line: number | null;
  severity: string | null;
  comment: string;
  suggestion: string | null;
};

type ReviewItem = {
  id: number;
  repository_id: number;
  repo_full_name: string | null;
  pr_number: number;
  pr_title: string | null;
  pr_author: string | null;
  trigger_type: string;
  engine: string | null;
  model: string | null;
  enabled_features: string[];
  focus_areas: string[];
  analysis_mode: string | null;
  overall_severity: string | null;
  overall_success: boolean | null;
  error_message: string | null;
  inline_comments_count: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
};

type ReviewDetail = {
  id: number;
  engine: string | null;
  model: string | null;
  head_sha: string | null;
  enabled_features: string[];
  focus_areas: string[];
  analysis_mode: string | null;
  summary_markdown: string | null;
  inline_comments_count: number;
  overall_success: boolean | null;
  error_message: string | null;
  inline_comments: InlineComment[];
};

type ReviewsResponse = {
  reviews: ReviewItem[];
  total: number;
  limit: number;
  offset: number;
};

const PAGE_SIZE = 20;

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
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function renderFocusChips(focusAreas: string[] | null | undefined): ReactNode {
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

function renderStatusChip(status: boolean | null): ReactNode {
  if (status === true) {
    return (
      <Chip color="success" variant="flat" size="sm">
        成功
      </Chip>
    );
  }
  if (status === false) {
    return (
      <Chip color="danger" variant="flat" size="sm">
        失败
      </Chip>
    );
  }
  return (
    <Chip color="default" variant="flat" size="sm">
      进行中
    </Chip>
  );
}

function shortText(text: string | null, max = 36): string {
  if (!text) return '—';
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
}

export default function AdminReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, ReviewDetail>>({});

  const currentPage = useMemo(() => Math.floor(offset / PAGE_SIZE) + 1, [offset]);
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const fetchReviews = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/reviews?limit=${PAGE_SIZE}&offset=${offset}`);
      if (!res.ok) {
        throw new Error('获取审查历史失败');
      }
      const data = (await res.json()) as ReviewsResponse;
      setReviews(data.reviews);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof Error) setError(err.message);
      else setError('获取审查历史失败');
      setReviews([]);
      setTotal(0);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [offset]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const loadDetail = useCallback(async (reviewId: number) => {
    if (detailCache[reviewId]) return;
    setDetailLoadingId(reviewId);
    try {
      const res = await apiFetch(`/api/reviews/${reviewId}`);
      if (!res.ok) return;
      const data = (await res.json()) as ReviewDetail;
      setDetailCache((prev) => ({ ...prev, [reviewId]: data }));
    } finally {
      setDetailLoadingId(null);
    }
  }, [detailCache]);

  const handleRowClick = useCallback((reviewId: number) => {
    if (expandedId === reviewId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(reviewId);
    void loadDetail(reviewId);
  }, [expandedId, loadDetail]);

  const renderExpanded = (reviewId: number): ReactNode => {
    if (detailLoadingId === reviewId && !detailCache[reviewId]) {
      return (
        <div className="flex items-center justify-center py-8 text-default-500">
          <Spinner size="sm" />
          <span className="ml-2">加载审查详情中...</span>
        </div>
      );
    }

    const detail = detailCache[reviewId];
    if (!detail) {
      return <div className="py-6 text-center text-default-500">暂无详情</div>;
    }

    return (
      <div className="p-4 space-y-4 bg-default-50 border-t border-default-200">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <div>
            <span className="text-default-500 mr-2">Commit</span>
            <code className="text-xs">{detail.head_sha?.slice(0, 7) || '—'}</code>
          </div>
          <div>
            <span className="text-default-500 mr-2">审查引擎</span>
            <span>{detail.engine || '—'}</span>
          </div>
          <div>
            <span className="text-default-500 mr-2">模型 ID</span>
            <span>{detail.model || '—'}</span>
          </div>
          <div>
            <span className="text-default-500 mr-2">审查模式</span>
            <span>{detail.analysis_mode || '—'}</span>
          </div>
          <div>
            <span className="text-default-500 mr-2">审查功能</span>
            <span>{detail.enabled_features?.join(', ') || '—'}</span>
          </div>
        </div>

        <div>
          <p className="m-0 mb-2 text-sm text-default-500">审查方向</p>
          {renderFocusChips(detail.focus_areas)}
        </div>

        {detail.error_message ? (
          <div className="rounded border border-danger-200 bg-danger-50 p-3 text-danger-700 text-sm whitespace-pre-wrap">
            {detail.error_message}
          </div>
        ) : null}

        {detail.summary_markdown ? (
          <div>
            <p className="m-0 mb-2 text-sm text-default-500">审查摘要</p>
            <pre className="m-0 rounded border border-default-200 bg-white p-3 text-sm whitespace-pre-wrap">
              {detail.summary_markdown}
            </pre>
          </div>
        ) : null}

        <div>
          <p className="m-0 mb-2 text-sm text-default-500">行级评论 ({detail.inline_comments_count})</p>
          {detail.inline_comments.length === 0 ? (
            <p className="m-0 text-sm text-default-400">无行级评论</p>
          ) : (
            <div className="space-y-2">
              {detail.inline_comments.map((comment) => (
                <div key={comment.id} className="rounded border border-default-200 bg-white p-3">
                  <div className="flex items-center justify-between gap-2 mb-1 text-xs text-default-500">
                    <span>
                      {comment.file_path}:{comment.new_line ?? comment.old_line ?? '-'}
                    </span>
                    {comment.severity ? (
                      <Chip
                        size="sm"
                        variant="flat"
                        color={comment.severity === 'high' || comment.severity === 'critical' ? 'danger' : 'warning'}
                        className="h-5 text-[10px]"
                      >
                        {comment.severity}
                      </Chip>
                    ) : null}
                  </div>
                  <p className="m-0 text-sm whitespace-pre-wrap">{comment.comment}</p>
                  {comment.suggestion ? (
                    <pre className="mt-2 mb-0 rounded border border-default-200 bg-default-50 p-2 text-xs whitespace-pre-wrap">
                      {comment.suggestion}
                    </pre>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      <Head>
        <title>审查历史 - 管理后台</title>
      </Head>

      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="审查历史"
          actions={
            <div className="flex items-center gap-2">
              <Button
                isIconOnly
                variant="bordered"
                size="sm"
                onPress={() => fetchReviews(true)}
                isDisabled={refreshing}
                aria-label="刷新审查历史"
              >
                <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
              </Button>
              <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
                返回管理后台
              </Button>
            </div>
          }
        />

        {loading ? (
          <>
            <div className="h-8 w-40 rounded bg-default-200 animate-pulse" />
            <div className="h-64 rounded border border-default-200 bg-default-50 animate-pulse" />
          </>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 text-default-500 gap-4">
            <p className="m-0">{error}</p>
            <Button color="primary" onPress={() => fetchReviews()}>
              重试
            </Button>
          </div>
        ) : reviews.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-default-500">
            <p className="m-0">暂无审查记录</p>
          </div>
        ) : (
          <>
            <Table aria-label="审查历史列表" removeWrapper>
              <TableHeader>
                <TableColumn>仓库</TableColumn>
                <TableColumn>PR</TableColumn>
                <TableColumn>触发</TableColumn>
                <TableColumn>引擎</TableColumn>
                <TableColumn>审查方向</TableColumn>
                <TableColumn>耗时</TableColumn>
                <TableColumn>状态</TableColumn>
                <TableColumn>失败原因</TableColumn>
                <TableColumn>时间</TableColumn>
                <TableColumn> </TableColumn>
              </TableHeader>
              <TableBody>
                {reviews.flatMap((review): JSX.Element[] => {
                  const rows: JSX.Element[] = [];
                  const isExpanded = expandedId === review.id;
                  rows.push(
                    <TableRow
                      key={review.id}
                      className="cursor-pointer"
                      onClick={() => handleRowClick(review.id)}
                    >
                      <TableCell>{review.repo_full_name || `#${review.repository_id}`}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="text-xs text-primary">#{review.pr_number}</span>
                          <span className="text-xs text-default-500 truncate max-w-[220px]">{review.pr_title || '-'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Chip size="sm" variant="flat" color={review.trigger_type === 'manual' ? 'secondary' : 'primary'}>
                          {review.trigger_type}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <Chip size="sm" variant="flat" className="w-fit">
                            {review.engine || 'claude_code'}
                          </Chip>
                          <span className="text-[11px] text-default-500 mt-1">
                            {review.model || '—'}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>{renderFocusChips(review.focus_areas)}</TableCell>
                      <TableCell>{formatDuration(review.duration_seconds)}</TableCell>
                      <TableCell>{renderStatusChip(review.overall_success)}</TableCell>
                      <TableCell>
                        <span className="text-xs text-default-500" title={review.error_message || ''}>
                          {review.overall_success === false ? shortText(review.error_message) : '—'}
                        </span>
                      </TableCell>
                      <TableCell>{formatTime(review.started_at)}</TableCell>
                      <TableCell>{isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</TableCell>
                    </TableRow>
                  );

                  if (isExpanded) {
                    rows.push(
                      <TableRow key={`${review.id}-detail`}>
                        <TableCell colSpan={10} className="p-0">
                          {renderExpanded(review.id)}
                        </TableCell>
                      </TableRow>
                    );
                  }
                  return rows;
                })}
              </TableBody>
            </Table>

            {totalPages > 1 ? (
              <div className="flex justify-center">
                <Pagination
                  page={currentPage}
                  total={totalPages}
                  onChange={(page) => setOffset((page - 1) * PAGE_SIZE)}
                  showControls
                />
              </div>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}

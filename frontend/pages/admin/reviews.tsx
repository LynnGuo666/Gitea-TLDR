import Head from 'next/head';
import Link from 'next/link';
import { useEffect, useState, useCallback } from 'react';
import {
  Button,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Chip,
  Select,
  SelectItem,
  Spinner,
  Pagination,
} from '@heroui/react';
import { ArrowLeft, ChevronDown, ChevronUp, RefreshCw, AlertCircle, Clock, CheckCircle2, XCircle } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';

// --- Types ---

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

// --- Helpers ---

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

function truncate(str: string | null, len: number): string {
  if (!str) return '—';
  return str.length > len ? str.substring(0, len) + '...' : str;
}

// --- Component ---

export default function AdminReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20; // Default limit per page

  // Filter state
  // "all" | "true" | "false"
  const [successFilter, setSuccessFilter] = useState<string>('all');

  // Expansion state
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailsCache, setDetailsCache] = useState<Record<number, ReviewDetail>>({});
  const [detailLoading, setDetailLoading] = useState(false);

  // Fetch list
  const fetchReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let query = `/api/reviews?limit=${limit}&offset=${offset}`;
      if (successFilter !== 'all') {
        query += `&success=${successFilter}`;
      }
      const res = await apiFetch(query);
      if (!res.ok) {
        throw new Error(`Failed to fetch reviews: ${res.statusText}`);
      }
      const data: ReviewsResponse = await res.json();
      setReviews(data.reviews);
      setTotal(data.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }, [offset, successFilter]);

  // Initial load & when params change
  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  // Fetch detail for expansion
  const toggleRow = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }

    setExpandedId(id);
    if (detailsCache[id]) {
      return; // Already cached
    }

    setDetailLoading(true);
    try {
      const res = await apiFetch(`/api/reviews/${id}`);
      if (res.ok) {
        const detail: ReviewDetail = await res.json();
        setDetailsCache((prev) => ({ ...prev, [id]: detail }));
      }
    } catch (err) {
      console.error('Failed to load review detail', err);
    } finally {
      setDetailLoading(false);
    }
  };

  // Pagination handler
  const handlePageChange = (page: number) => {
    setOffset((page - 1) * limit);
  };

  const renderExpandedContent = (id: number) => {
    if (detailLoading && !detailsCache[id]) {
      return (
        <div className="flex justify-center p-8 text-default-400">
          <Spinner size="sm" color="default" />
          <span className="ml-2">Loading details...</span>
        </div>
      );
    }

    const detail = detailsCache[id];
    if (!detail) return <div className="p-4 text-danger">Failed to load details.</div>;

    return (
      <div className="p-4 bg-default-50/50 rounded-lg space-y-4 text-sm border-t border-default-100 shadow-inner">
        {/* Meta Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-default-500 mb-2">
          <div>
            <span className="font-semibold block text-default-700 text-xs uppercase tracking-wider">HEAD</span>
            {detail.head_branch || '—'} <span className="text-xs opacity-70 font-mono">({truncate(detail.head_sha, 7)})</span>
          </div>
          <div>
            <span className="font-semibold block text-default-700 text-xs uppercase tracking-wider">BASE</span>
            {detail.base_branch || '—'}
          </div>
          <div>
            <span className="font-semibold block text-default-700 text-xs uppercase tracking-wider">DIFF SIZE</span>
            {detail.diff_size_bytes ? `${Math.round(detail.diff_size_bytes / 1024)} KB` : '—'}
          </div>
          <div>
            <span className="font-semibold block text-default-700 text-xs uppercase tracking-wider">FOCUS AREAS</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {detail.focus_areas && detail.focus_areas.length > 0 ? (
                detail.focus_areas.map((area) => (
                  <Chip key={area} size="sm" variant="flat" className="h-5 text-[10px] px-1 bg-default-200">
                    {area}
                  </Chip>
                ))
              ) : (
                <span>—</span>
              )}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {detail.error_message && (
          <div className="bg-danger-50 text-danger p-3 rounded-md border border-danger-200 flex items-start gap-2">
            <AlertCircle size={16} className="mt-0.5 shrink-0" />
            <pre className="whitespace-pre-wrap font-mono text-xs">{detail.error_message}</pre>
          </div>
        )}

        {/* Summary */}
        {detail.summary_markdown && (
          <div className="space-y-1">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-default-500">Review Summary</h4>
            <div className="bg-white dark:bg-black/20 border border-default-200 rounded p-4">
               <pre className="whitespace-pre-wrap font-sans text-default-700 leading-relaxed text-sm">
                 {detail.summary_markdown}
               </pre>
            </div>
          </div>
        )}

        {/* Inline Comments */}
        {detail.inline_comments && detail.inline_comments.length > 0 && (
          <div className="space-y-2">
             <h4 className="text-xs font-semibold uppercase tracking-wider text-default-500">
               Inline Comments ({detail.inline_comments.length})
             </h4>
             <div className="grid gap-2">
               {detail.inline_comments.map((comment, idx) => (
                 <div key={comment.id || idx} className="bg-white dark:bg-black/20 border-l-4 border-default-300 p-3 rounded-r shadow-sm text-sm">
                    <div className="flex justify-between items-start mb-1">
                      <div className="font-mono text-xs text-default-500">
                        {comment.file_path}:{comment.new_line || comment.old_line || '?'}
                      </div>
                      {comment.severity && (
                        <Chip size="sm" color={comment.severity === 'error' ? 'danger' : 'warning'} variant="flat" className="h-5 text-[10px]">
                          {comment.severity}
                        </Chip>
                      )}
                    </div>
                    <div className="text-default-800">{comment.comment}</div>
                 </div>
               ))}
             </div>
          </div>
        )}
        
        {/* Empty state for comments/summary if success but nothing found */}
        {!detail.error_message && !detail.summary_markdown && (!detail.inline_comments || detail.inline_comments.length === 0) && (
           <div className="text-center py-6 text-default-400 italic">
             No feedback generated for this review.
           </div>
        )}
      </div>
    );
  };

  return (
    <>
      <Head>
        <title>审查历史 - 管理后台</title>
      </Head>

      <div className="max-w-[1100px] mx-auto flex flex-col gap-6 pb-20">
        <PageHeader
          title="审查历史"
          actions={
            <div className="flex items-center gap-3">
              <Select
                aria-label="Filter status"
                placeholder="全部状态"
                selectedKeys={[successFilter]}
                onChange={(e) => {
                  setSuccessFilter(e.target.value);
                  setOffset(0); // Reset to page 1 on filter change
                }}
                className="w-32"
                size="sm"
                disallowEmptySelection
              >
                <SelectItem key="all" textValue="全部">全部</SelectItem>
                <SelectItem key="true" textValue="成功">成功</SelectItem>
                <SelectItem key="false" textValue="失败">失败</SelectItem>
              </Select>

              <Button
                isIconOnly
                variant="flat"
                size="sm"
                onClick={fetchReviews}
                isLoading={loading}
              >
                <RefreshCw size={18} />
              </Button>

              <div className="h-6 w-px bg-default-300 mx-1" />

              <Button
                as={Link}
                href="/admin"
                variant="bordered"
                size="sm"
                startContent={<ArrowLeft size={16} />}
              >
                返回管理后台
              </Button>
            </div>
          }
        />

        {/* Content Area */}
        {loading && reviews.length === 0 ? (
          <div className="space-y-4">
            <div className="h-10 w-full rounded bg-default-100 animate-pulse" />
            <div className="h-64 w-full rounded border border-default-200 bg-default-50 animate-pulse" />
          </div>
        ) : error ? (
          <div className="p-8 text-center rounded-lg border border-danger-200 bg-danger-50 text-danger-600">
            <AlertCircle className="mx-auto mb-2" size={32} />
            <p>无法加载审查历史: {error}</p>
            <Button size="sm" color="danger" variant="light" className="mt-4" onClick={fetchReviews}>
              重试
            </Button>
          </div>
        ) : reviews.length === 0 ? (
          <div className="p-12 text-center rounded-lg border border-dashed border-default-300 bg-default-50 text-default-500">
            <div className="mx-auto bg-default-100 p-4 rounded-full w-16 h-16 flex items-center justify-center mb-4">
               <Clock size={32} className="opacity-50" />
            </div>
            <p className="text-lg font-medium">暂无审查记录</p>
            <p className="text-sm opacity-70 mt-1">这里将显示所有自动或手动触发的代码审查历史。</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <Table aria-label="Review history table" selectionMode="none" className="bg-transparent" shadow="sm">
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
                {reviews.reduce((acc: JSX.Element[], review) => {
                  const isExpanded = expandedId === review.id;
                  
                  // Main Row
                  acc.push(
                    <TableRow 
                      key={review.id} 
                      className="cursor-pointer transition-colors hover:bg-default-100/50 group"
                      onClick={() => toggleRow(review.id)}
                    >
                      <TableCell>
                        <span className="font-medium text-default-700">{review.repo_full_name || '—'}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="text-primary font-mono text-xs">#{review.pr_number}</span>
                          <span className="text-default-600 text-xs truncate max-w-[180px]" title={review.pr_title || ''}>
                            {truncate(review.pr_title, 25)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Chip size="sm" variant="flat" className="h-6 text-[10px] bg-default-100 text-default-600">
                           {review.trigger_type}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                           <span className="text-sm text-default-700">{review.provider_name || '—'}</span>
                           <span className="text-[10px] text-default-400 font-mono scale-90 origin-left">
                             {review.model_name || ''}
                           </span>
                        </div>
                      </TableCell>
                      <TableCell>
                         <span className="text-default-500 font-mono text-xs">
                           {formatDuration(review.duration_seconds)}
                         </span>
                      </TableCell>
                      <TableCell>
                        {review.overall_success === true ? (
                          <Chip startContent={<CheckCircle2 size={12} />} size="sm" color="success" variant="flat" className="h-6 text-xs px-1">
                            成功
                          </Chip>
                        ) : review.overall_success === false ? (
                          <Chip startContent={<XCircle size={12} />} size="sm" color="danger" variant="flat" className="h-6 text-xs px-1">
                            失败
                          </Chip>
                        ) : (
                          <Chip size="sm" className="bg-default-200 text-default-500 h-6 text-xs px-1">
                            进行中
                          </Chip>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col text-xs text-default-500">
                           <span>{formatTime(review.started_at).split(' ')[0]}</span>
                           <span className="opacity-70">{formatTime(review.started_at).split(' ')[1]}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                         {isExpanded ? <ChevronUp size={16} className="text-default-400" /> : <ChevronDown size={16} className="text-default-300 group-hover:text-default-500" />}
                      </TableCell>
                    </TableRow>
                  );

                  // Detail Row (if expanded)
                  if (isExpanded) {
                    acc.push(
                      <TableRow key={`${review.id}-detail`} className="hover:bg-transparent">
                        <TableCell colSpan={8} className="p-0 border-b border-default-100">
                          {renderExpandedContent(review.id)}
                        </TableCell>
                      </TableRow>
                    );
                  }

                  return acc;
                }, [])}
              </TableBody>
            </Table>

            {/* Pagination */}
            {total > limit && (
              <div className="flex justify-center mt-4">
                <Pagination
                  total={Math.ceil(total / limit)}
                  page={(offset / limit) + 1}
                  onChange={handlePageChange}
                  showControls
                  size="sm"
                  variant="light"
                />
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

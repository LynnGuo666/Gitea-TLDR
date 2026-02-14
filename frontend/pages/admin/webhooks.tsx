import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
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

type WebhookLogItem = {
  id: number;
  request_id: string;
  repository_id: number;
  event_type: string;
  status: string;
  error_message: string | null;
  processing_time_ms: number | null;
  retry_count: number;
  created_at: string;
};

type WebhookLogDetail = WebhookLogItem & {
  payload: unknown;
  updated_at: string;
};

const PAGE_SIZE = 20;

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function statusColor(status: string): 'success' | 'danger' | 'warning' | 'default' {
  const normalized = status.toLowerCase();
  if (normalized === 'success' || normalized === 'ok' || normalized === 'completed') return 'success';
  if (normalized === 'failed' || normalized === 'error') return 'danger';
  if (normalized === 'pending' || normalized === 'queued' || normalized === 'running') return 'warning';
  return 'default';
}

function toPrettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export default function AdminWebhooksPage() {
  const [logs, setLogs] = useState<WebhookLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [offset, setOffset] = useState(0);

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null);
  const [detailCache, setDetailCache] = useState<Record<number, WebhookLogDetail>>({});

  const fetchLogs = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
      });
      if (statusFilter !== 'all') {
        params.set('status', statusFilter);
      }

      const res = await apiFetch(`/api/admin/webhooks/logs?${params.toString()}`);
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          throw new Error('当前账号没有 Webhook 日志访问权限');
        }
        if (res.status === 503) {
          throw new Error('数据库未启用，无法读取 Webhook 日志');
        }
        throw new Error('获取 Webhook 日志失败');
      }

      const data = (await res.json()) as WebhookLogItem[];
      setLogs(data);
    } catch (err) {
      setLogs([]);
      setError(err instanceof Error ? err.message : '获取 Webhook 日志失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [offset, statusFilter]);

  useEffect(() => {
    void fetchLogs();
  }, [fetchLogs]);

  const canPrev = offset > 0;
  const canNext = logs.length === PAGE_SIZE;

  const page = useMemo(() => Math.floor(offset / PAGE_SIZE) + 1, [offset]);

  const loadDetail = useCallback(async (id: number) => {
    if (detailCache[id]) return;

    setDetailLoadingId(id);
    try {
      const res = await apiFetch(`/api/admin/webhooks/logs/${id}`);
      if (!res.ok) return;
      const data = (await res.json()) as WebhookLogDetail;
      setDetailCache((prev) => ({ ...prev, [id]: data }));
    } finally {
      setDetailLoadingId(null);
    }
  }, [detailCache]);

  const toggleRow = (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    void loadDetail(id);
  };

  return (
    <>
      <Head>
        <title>Webhook 日志 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="Webhook 日志"
          actions={
            <div className="flex items-center gap-2">
              <Button
                isIconOnly
                variant="bordered"
                size="sm"
                onPress={() => fetchLogs(true)}
                isDisabled={refreshing || loading}
                aria-label="刷新 webhook 日志"
              >
                <RefreshCw size={16} className={refreshing || loading ? 'animate-spin' : ''} />
              </Button>
              <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
                返回管理后台
              </Button>
            </div>
          }
        />

        {error ? <div className="rounded-lg border border-danger-200 bg-danger-50 p-3 text-danger-700 text-sm">{error}</div> : null}

        <section className="rounded-lg border border-default-200 p-4 sm:p-5 flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-sm text-default-500 inline-flex items-center gap-2">
              状态过滤
              <select
                className="rounded-md border border-default-200 bg-content1 px-2 py-1"
                value={statusFilter}
                onChange={(e) => {
                  setOffset(0);
                  setStatusFilter(e.target.value);
                }}
              >
                <option value="all">全部</option>
                <option value="success">success</option>
                <option value="failed">failed</option>
                <option value="pending">pending</option>
                <option value="error">error</option>
              </select>
            </label>
            <span className="text-sm text-default-500">当前页记录: {logs.length}</span>
          </div>

          {loading ? (
            <div className="py-10 text-center text-default-500">加载日志中...</div>
          ) : logs.length === 0 ? (
            <div className="py-10 text-center text-default-500">暂无日志记录</div>
          ) : (
            <div className="rounded-lg border border-default-200 overflow-hidden">
              <Table aria-label="Webhook 日志表" removeWrapper>
                <TableHeader>
                  <TableColumn>时间</TableColumn>
                  <TableColumn>事件</TableColumn>
                  <TableColumn>状态</TableColumn>
                  <TableColumn>耗时</TableColumn>
                  <TableColumn>重试</TableColumn>
                  <TableColumn>错误</TableColumn>
                  <TableColumn> </TableColumn>
                </TableHeader>
                <TableBody>
                  {logs.flatMap((log) => {
                    const isExpanded = expandedId === log.id;
                    const rows: JSX.Element[] = [];

                    rows.push(
                      <TableRow key={log.id} className="cursor-pointer" onClick={() => toggleRow(log.id)}>
                        <TableCell>
                          <div className="text-sm">{formatTime(log.created_at)}</div>
                          <div className="text-xs text-default-400">#{log.id} · repo:{log.repository_id}</div>
                        </TableCell>
                        <TableCell>
                          <div className="font-medium">{log.event_type}</div>
                          <div className="text-xs text-default-400">{log.request_id}</div>
                        </TableCell>
                        <TableCell>
                          <Chip size="sm" color={statusColor(log.status)} variant="flat">{log.status}</Chip>
                        </TableCell>
                        <TableCell>{log.processing_time_ms !== null ? `${log.processing_time_ms} ms` : '—'}</TableCell>
                        <TableCell>{log.retry_count}</TableCell>
                        <TableCell>
                          <span className="text-xs text-default-500" title={log.error_message || ''}>
                            {log.error_message ? (log.error_message.length > 40 ? `${log.error_message.slice(0, 40)}...` : log.error_message) : '—'}
                          </span>
                        </TableCell>
                        <TableCell>{isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</TableCell>
                      </TableRow>
                    );

                    if (isExpanded) {
                      const detail = detailCache[log.id];
                      rows.push(
                        <TableRow key={`${log.id}-detail`}>
                          <TableCell colSpan={7} className="p-0">
                            {detailLoadingId === log.id && !detail ? (
                              <div className="py-8 text-center text-default-500 flex items-center justify-center gap-2">
                                <Spinner size="sm" />
                                <span>加载详情中...</span>
                              </div>
                            ) : detail ? (
                              <div className="border-t border-default-200 bg-default-50 p-4 flex flex-col gap-3">
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                                  <div>
                                    <span className="text-default-500 mr-2">请求 ID</span>
                                    <code className="text-xs">{detail.request_id}</code>
                                  </div>
                                  <div>
                                    <span className="text-default-500 mr-2">更新时间</span>
                                    <span>{formatTime(detail.updated_at)}</span>
                                  </div>
                                  <div>
                                    <span className="text-default-500 mr-2">状态</span>
                                    <Chip size="sm" color={statusColor(detail.status)} variant="flat">{detail.status}</Chip>
                                  </div>
                                </div>
                                <div>
                                  <p className="m-0 mb-2 text-sm text-default-500">Payload</p>
                                  <pre className="m-0 rounded border border-default-200 bg-content1 p-3 text-xs whitespace-pre-wrap overflow-x-auto max-h-80">
                                    {toPrettyJson(detail.payload)}
                                  </pre>
                                </div>
                                {detail.error_message ? (
                                  <div className="rounded border border-danger-200 bg-danger-50 p-3 text-xs text-danger-700 whitespace-pre-wrap">
                                    {detail.error_message}
                                  </div>
                                ) : null}
                              </div>
                            ) : (
                              <div className="py-8 text-center text-default-500">暂无详情</div>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    }

                    return rows;
                  })}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-default-500">第 {page} 页（每页 {PAGE_SIZE} 条）</div>
            <div className="flex items-center gap-2">
              <Button variant="bordered" size="sm" isDisabled={!canPrev} onPress={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}>
                上一页
              </Button>
              <Pagination
                page={page}
                total={Math.max(page, page + (canNext ? 1 : 0))}
                onChange={(nextPage) => setOffset((nextPage - 1) * PAGE_SIZE)}
                showControls={false}
                size="sm"
              />
              <Button variant="bordered" size="sm" isDisabled={!canNext} onPress={() => setOffset((prev) => prev + PAGE_SIZE)}>
                下一页
              </Button>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

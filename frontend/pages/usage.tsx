import Head from 'next/head';
import { useEffect, useState, useMemo } from 'react';
import {
  Button,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Chip,
} from '@heroui/react';
import { RefreshCw } from 'lucide-react';
import { apiFetch } from '../lib/api';
import PageHeader from '../components/PageHeader';

const USD_PER_MILLION_INPUT = 3;
const USD_PER_MILLION_OUTPUT = 15;

type UsageStat = {
  id: number;
  repository_id: number;
  review_session_id: number | null;
  date: string | null;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  gitea_api_calls: number;
  claude_api_calls: number;
  provider_api_calls: number;
  clone_operations: number;
};

type UsageSummary = {
  total_input_tokens: number;
  total_output_tokens: number;
  total_gitea_calls: number;
  total_claude_calls: number;
  total_provider_calls: number;
  total_clone_operations: number;
  review_count: number;
};

type StatsResponse = {
  summary: UsageSummary;
  details: UsageStat[];
};

export default function UsagePage() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);

  const fetchStats = async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await apiFetch('/api/stats');
      if (!res.ok) {
        if (res.status === 503) {
          setError('数据库未启用，无法获取统计数据');
        } else {
          setError('获取统计数据失败');
        }
        setStats(null);
      } else {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      setError('网络错误，无法连接服务器');
      setStats(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const totalTokens = useMemo(() => {
    if (!stats?.summary) return 0;
    return stats.summary.total_input_tokens + stats.summary.total_output_tokens;
  }, [stats]);

  const totalRequests = useMemo(() => {
    return stats?.summary?.total_provider_calls ?? stats?.summary?.total_claude_calls ?? 0;
  }, [stats]);

  const usdCost = useMemo(() => {
    if (!stats?.summary) return '0.00';
    const inputCost = (stats.summary.total_input_tokens / 1_000_000) * USD_PER_MILLION_INPUT;
    const outputCost = (stats.summary.total_output_tokens / 1_000_000) * USD_PER_MILLION_OUTPUT;
    return (inputCost + outputCost).toFixed(2);
  }, [stats]);

  const groupedByDate = useMemo(() => {
    if (!stats?.details?.length) return [];
    const groups: { [key: string]: { date: string; inputTokens: number; outputTokens: number; requests: number } } = {};

    for (const stat of stats.details) {
      const dateKey = stat.date || 'unknown';
      if (!groups[dateKey]) {
        groups[dateKey] = { date: dateKey, inputTokens: 0, outputTokens: 0, requests: 0 };
      }
      groups[dateKey].inputTokens += stat.estimated_input_tokens;
      groups[dateKey].outputTokens += stat.estimated_output_tokens;
      groups[dateKey].requests += stat.provider_api_calls ?? stat.claude_api_calls;
    }

    return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date));
  }, [stats]);

  if (loading) {
    return (
      <>
        <Head><title>用量 - LCPU AI Reviewer</title></Head>
        <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
          <div className="h-8 w-32 rounded bg-default-200 animate-pulse" />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, idx) => (
              <div key={idx} className="h-20 rounded border border-default-200 bg-default-50 animate-pulse" />
            ))}
          </div>
          <div className="h-64 rounded border border-default-200 bg-default-50 animate-pulse" />
        </div>
      </>
    );
  }

  return (
    <>
        <Head><title>用量 - LCPU AI Reviewer</title></Head>
        <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
          <PageHeader
            title="用量统计"
            actions={
              <div className="flex items-center gap-3">
              <Button
                isIconOnly
                variant="bordered"
              size="sm"
              onPress={() => fetchStats(true)}
              isDisabled={refreshing}
              aria-label="刷新统计"
            >
              <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
            </Button>
              <Chip variant="bordered" size="sm">
                <span className="text-default-500 mr-1">预计美元</span>
                <strong className="text-success">${usdCost}</strong>
              </Chip>
              </div>
            }
          />

        {error ? (
          <div className="flex flex-col items-center justify-center py-12 text-default-500 gap-4">
            <p className="m-0">{error}</p>
            <Button color="primary" onPress={() => fetchStats()}>重试</Button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-2">
              {[
                { label: '总 tokens', value: totalTokens },
                { label: '输入 tokens', value: stats?.summary?.total_input_tokens || 0 },
                { label: '输出 tokens', value: stats?.summary?.total_output_tokens || 0 },
                { label: 'API 调用', value: totalRequests },
                { label: '审查次数', value: stats?.summary?.review_count || 0 },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-lg border border-default-200 p-3">
                  <p className="m-0 text-default-500 text-sm">{label}</p>
                  <strong className="block mt-1 text-lg text-foreground">{value.toLocaleString()}</strong>
                </div>
              ))}
            </div>

            {groupedByDate.length > 0 ? (
              <div className="overflow-x-auto">
                <Table aria-label="用量明细">
                  <TableHeader>
                    <TableColumn>日期</TableColumn>
                    <TableColumn>输入 Tokens</TableColumn>
                    <TableColumn>输出 Tokens</TableColumn>
                    <TableColumn>请求</TableColumn>
                    <TableColumn>费用</TableColumn>
                  </TableHeader>
                  <TableBody>
                    {groupedByDate.map((entry) => {
                      const cost = (
                        (entry.inputTokens / 1_000_000) * USD_PER_MILLION_INPUT +
                        (entry.outputTokens / 1_000_000) * USD_PER_MILLION_OUTPUT
                      ).toFixed(2);
                      return (
                        <TableRow key={entry.date}>
                          <TableCell>{entry.date}</TableCell>
                          <TableCell>{entry.inputTokens.toLocaleString()}</TableCell>
                          <TableCell>{entry.outputTokens.toLocaleString()}</TableCell>
                          <TableCell>{entry.requests}</TableCell>
                          <TableCell>${cost}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-default-500">
                <p className="m-0">暂无使用记录</p>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

import Head from 'next/head';
import { useEffect, useState } from 'react';
import { Button, Chip } from '@heroui/react';
import { RefreshCw } from 'lucide-react';
import { apiFetch } from '../lib/api';
import PageHeader from '../components/PageHeader';
import type { ChangelogEntry, ChangelogResponse } from '../lib/types';

type ChipColor = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger';

const CHANGE_PREFIX_MAP: Array<{ prefix: string; label: string; color: ChipColor }> = [
  { prefix: '新增', label: '新增', color: 'success' },
  { prefix: '修复', label: '修复', color: 'danger' },
  { prefix: '安全', label: '安全', color: 'warning' },
  { prefix: '优化', label: '优化', color: 'primary' },
  { prefix: '重构', label: '重构', color: 'secondary' },
  { prefix: '测试', label: '测试', color: 'secondary' },
  { prefix: '调整', label: '调整', color: 'primary' },
  { prefix: '依赖', label: '依赖', color: 'default' },
  { prefix: '维护', label: '维护', color: 'default' },
  { prefix: '同步', label: '同步', color: 'default' },
];

function parseChange(change: string): { label: string; color: ChipColor; text: string } {
  for (const { prefix, label, color } of CHANGE_PREFIX_MAP) {
    if (change.startsWith(prefix + '：') || change.startsWith(prefix + ':')) {
      const sep = change.indexOf('：') !== -1 ? '：' : ':';
      return { label, color, text: change.slice(prefix.length + sep.length).trim() };
    }
  }
  return { label: '其他', color: 'default', text: change };
}

function VersionCard({ entry, isLatest }: { entry: ChangelogEntry; isLatest: boolean }) {
  return (
    <div className="flex gap-4 sm:gap-6">
      {/* 时间线轴 */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`w-3 h-3 rounded-full mt-1 ring-2 ring-offset-2 ring-offset-default-50 shrink-0 ${
            isLatest ? 'bg-primary ring-primary' : 'bg-default-300 ring-default-300'
          }`}
        />
        <div className="w-px flex-1 bg-default-200 mt-1" />
      </div>

      {/* 内容卡片 */}
      <div className="flex-1 pb-8 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-base font-bold text-foreground">v{entry.version}</span>
          {isLatest && (
            <Chip size="sm" color="primary" variant="flat">
              最新
            </Chip>
          )}
          <span className="text-xs text-default-400">{entry.date}</span>
        </div>

        <div className="rounded-lg border border-default-200 bg-content1 px-4 py-3 flex flex-col gap-2">
          {entry.changes.map((change, idx) => {
            const { label, color, text } = parseChange(change);
            return (
              <div key={idx} className="flex items-start gap-2">
                <Chip size="sm" color={color} variant="flat" className="shrink-0 mt-0.5">
                  {label}
                </Chip>
                <span className="text-sm text-foreground/80 leading-5">{text}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function ChangelogPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ChangelogResponse | null>(null);

  const fetchChangelog = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/changelog/json');
      if (!res.ok) throw new Error('获取更新日志失败');
      const json = await res.json() as ChangelogResponse;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchChangelog(); }, []);

  return (
    <>
      <Head>
        <title>更新日志</title>
      </Head>
      <div className="max-w-[780px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="更新日志"
          actions={
            <Button
              isIconOnly
              variant="bordered"
              size="sm"
              onPress={fetchChangelog}
              isDisabled={loading}
              aria-label="刷新"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </Button>
          }
        />

        {error && (
          <div className="p-3 bg-danger-50 border border-danger rounded-lg text-danger text-sm">
            {error}
          </div>
        )}

        {loading && !data ? (
          <div className="py-12 text-center rounded-lg border border-default-200 text-default-400">
            加载中...
          </div>
        ) : data && data.history.length > 0 ? (
          <div className="flex flex-col">
            {data.history.map((entry, idx) => (
              <VersionCard key={entry.version} entry={entry} isLatest={idx === 0} />
            ))}
          </div>
        ) : !error ? (
          <div className="py-12 text-center rounded-lg border border-default-200 text-default-400">
            暂无更新日志
          </div>
        ) : null}
      </div>
    </>
  );
}

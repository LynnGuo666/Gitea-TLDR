import Head from 'next/head';
import { useState } from 'react';
import { Chip } from '@heroui/react';
import PageHeader from '../../components/PageHeader';
import EmptyState from '../../components/EmptyState';
import ErrorState from '../../components/ErrorState';
import RunDetailModal from '../../components/RunDetailModal';
import { useApiFetch } from '../../lib/hooks';
import { relativeTime } from '../../lib/utils';
import { AnalysisRunSummary } from '../../lib/types';

export default function AdminReviewsPage() {
  const { data, loading, error, refresh } = useApiFetch<{ runs: AnalysisRunSummary[] }>(
    '/api/v2/runs?kind=review&limit=100&offset=0'
  );
  const runs = data?.runs || [];
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  return (
    <>
      <Head><title>Review Runs - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Review Runs (Admin)" subtitle="全部 PR 审查运行记录，点击查看详情" />
        <div className="mt-4 grid gap-3">
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={refresh} className="text-sm text-primary hover:underline">重试</button>} />
          ) : runs.length === 0 ? (
            <EmptyState title="暂无 PR 审查记录" description="尚未触发过 PR 审查。" />
          ) : (
            runs.map((run) => (
              <button
                key={run.id}
                onClick={() => setSelectedRunId(run.id)}
                className="text-left border-b border-divider py-3 hover:bg-default-100/60 rounded-md px-2 -mx-2 transition-colors"
              >
                <div className="font-medium">#{run.external_number} {run.external_title || 'Untitled'}</div>
                <div className="text-sm text-default-500 flex items-center gap-2 flex-wrap">
                  <span>{run.repo_full_name || `repo ${run.repository_id}`}</span>
                  <Chip size="sm" variant="flat" color={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'danger' : 'primary'}>{run.status}</Chip>
                  <span>{run.effective_engine || 'engine unknown'}</span>
                  {run.started_at && <span>· {relativeTime(run.started_at)}</span>}
                </div>
                {run.error_message && <div className="mt-1 text-sm text-danger">{run.error_message}</div>}
              </button>
            ))
          )}
        </div>
      </div>
      <RunDetailModal runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
    </>
  );
}

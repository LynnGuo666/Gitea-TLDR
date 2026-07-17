import Head from 'next/head';
import PageHeader from '../components/PageHeader';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import { useApiFetch } from '../lib/hooks';
import { relativeTime } from '../lib/utils';
import { AnalysisRunSummary } from '../lib/types';

export default function ReviewsPage() {
  const { data, loading, error, refresh } = useApiFetch<{ runs: AnalysisRunSummary[] }>(
    '/api/v2/runs?kind=review&limit=50&offset=0'
  );
  const runs = data?.runs || [];

  return (
    <>
      <Head><title>Review Runs - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Review Runs" subtitle="PR 审查运行记录" />
        <div className="mt-4 grid gap-3">
          {loading ? (
            <div className="text-sm text-default-400">加载中…</div>
          ) : error ? (
            <ErrorState message={error} action={<button onClick={refresh} className="text-sm text-primary hover:underline">重试</button>} />
          ) : runs.length === 0 ? (
            <EmptyState title="暂无 PR 审查记录" description="尚未触发过 PR 审查。" />
          ) : (
            runs.map((run) => (
              <div key={run.id} className="border-b border-divider py-3">
                <div className="font-medium">#{run.external_number} {run.external_title || 'Untitled'}</div>
                <div className="text-sm text-default-500">
                  {run.repo_full_name || `repo ${run.repository_id}`} · {run.status} · {run.effective_engine || 'engine unknown'}
                  {run.started_at ? ` · ${relativeTime(run.started_at)}` : ''}
                </div>
                {run.error_message && <div className="mt-1 text-sm text-danger">{run.error_message}</div>}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

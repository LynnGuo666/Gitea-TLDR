import Head from 'next/head';
import { useEffect, useState } from 'react';
import PageHeader from '../components/PageHeader';
import { apiFetch } from '../lib/api';
import { AnalysisRunSummary } from '../lib/types';

export default function IssuesPage() {
  const [runs, setRuns] = useState<AnalysisRunSummary[]>([]);

  useEffect(() => {
    apiFetch('/api/v2/runs?kind=issue&limit=50&offset=0')
      .then((res) => res.json())
      .then((data) => setRuns(data.runs || []))
      .catch(() => setRuns([]));
  }, []);

  return (
    <>
      <Head><title>Issue Runs - Gitea TLDR</title></Head>
      <div className="max-w-[1100px] mx-auto">
        <PageHeader title="Issue Runs" subtitle="Issue 分析运行记录" />
        <div className="mt-4 grid gap-3">
          {runs.map((run) => (
            <div key={run.id} className="border-b border-divider py-3">
              <div className="font-medium">#{run.external_number} {run.external_title || 'Untitled'}</div>
              <div className="text-sm text-default-500">{run.repo_full_name || `repo ${run.repository_id}`} · {run.status} · {run.effective_model || 'model unknown'}</div>
              {run.summary_markdown && <p className="mt-2 line-clamp-2 text-sm">{run.summary_markdown}</p>}
              {run.error_message && <div className="mt-1 text-sm text-danger">{run.error_message}</div>}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

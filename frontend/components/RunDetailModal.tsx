import { useEffect, useState } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, Chip, Divider } from '@heroui/react';
import { apiFetch } from '../lib/api';
import { readErrorMessage } from '../lib/utils';
import { AnalysisRunDetail, AnalysisAnnotation } from '../lib/types';

type RunDetailModalProps = {
  runId: number | null;
  onClose: () => void;
};

/** 运行详情弹窗：拉取 /runs/{id} + /runs/{id}/annotations 展示摘要与行级注释。 */
export default function RunDetailModal({ runId, onClose }: RunDetailModalProps) {
  const [detail, setDetail] = useState<AnalysisRunDetail | null>(null);
  const [annotations, setAnnotations] = useState<AnalysisAnnotation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (runId == null) {
      setDetail(null);
      setAnnotations([]);
      setError('');
      return;
    }
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([
      apiFetch(`/api/v2/runs/${runId}`),
      apiFetch(`/api/v2/runs/${runId}/annotations`),
    ])
      .then(async ([runRes, annoRes]) => {
        if (!runRes.ok) throw new Error(await readErrorMessage(runRes, '加载运行详情失败'));
        const run = (await runRes.json()) as AnalysisRunDetail;
        const annos = annoRes.ok ? ((await annoRes.json()) as { annotations: AnalysisAnnotation[] }).annotations || [] : [];
        if (active) {
          setDetail(run);
          setAnnotations(annos);
        }
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : '加载失败');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [runId]);

  const isOpen = runId != null;

  return (
    <Modal isOpen={isOpen} onOpenChange={(open) => !open && onClose()} size="lg" scrollBehavior="inside">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          <span className="text-base">
            {detail ? `#${detail.external_number} ${detail.external_title || 'Untitled'}` : '运行详情'}
          </span>
          {detail && (
            <div className="flex items-center gap-2 flex-wrap text-xs text-default-500">
              <span>{detail.repo_full_name || `repo ${detail.repository_id}`}</span>
              <Chip size="sm" variant="flat" color={detail.status === 'completed' ? 'success' : detail.status === 'failed' ? 'danger' : 'primary'}>
                {detail.status}
              </Chip>
              {detail.effective_engine && <Chip size="sm" variant="flat">{detail.effective_engine}</Chip>}
              {detail.effective_model && <span>{detail.effective_model}</span>}
            </div>
          )}
        </ModalHeader>
        <ModalBody className="pb-6">
          {loading ? (
            <p className="text-sm text-default-400">加载中…</p>
          ) : error ? (
            <p className="text-sm text-danger">{error}</p>
          ) : detail ? (
            <div className="flex flex-col gap-4">
              {detail.error_message && (
                <div className="rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
                  {detail.error_message}
                </div>
              )}

              {detail.summary_markdown && (
                <section>
                  <h3 className="text-sm font-semibold mb-1">摘要</h3>
                  <p className="text-sm text-foreground/80 whitespace-pre-wrap m-0">{detail.summary_markdown}</p>
                </section>
              )}

              {detail.related_issues.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold mb-1">相关问题（{detail.related_issue_count}）</h3>
                  <ul className="m-0 pl-4 text-sm text-foreground/80 list-disc">
                    {detail.related_issues.map((issue, idx) => (
                      <li key={idx}>{String((issue as { title?: string })?.title ?? issue)}</li>
                    ))}
                  </ul>
                </section>
              )}

              {detail.solution_suggestions.length > 0 && (
                <section>
                  <h3 className="text-sm font-semibold mb-1">解决建议（{detail.solution_count}）</h3>
                  <ul className="m-0 pl-4 text-sm text-foreground/80 list-disc">
                    {detail.solution_suggestions.map((s, idx) => (
                      <li key={idx}>{String(s)}</li>
                    ))}
                  </ul>
                </section>
              )}

              <Divider />

              <section>
                <h3 className="text-sm font-semibold mb-2">行级注释（{annotations.length}）</h3>
                {annotations.length === 0 ? (
                  <p className="text-sm text-default-400 m-0">无行级注释。</p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {annotations.map((a) => (
                      <div key={a.id} className="rounded-md border border-divider p-3 text-sm">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <code className="text-xs bg-default-100 px-1.5 py-0.5 rounded">{a.file_path || '(无文件)'}</code>
                          {a.new_line && <span className="text-xs text-default-500">L{a.new_line}</span>}
                          {a.severity && <Chip size="sm" variant="flat" color={a.severity === 'critical' || a.severity === 'high' ? 'danger' : a.severity === 'medium' ? 'warning' : 'default'}>{a.severity}</Chip>}
                        </div>
                        <p className="m-0 text-foreground/80 whitespace-pre-wrap">{a.body}</p>
                        {a.suggestion && (
                          <pre className="mt-2 m-0 p-2 rounded bg-default-100 text-xs overflow-x-auto whitespace-pre-wrap"><code>{a.suggestion}</code></pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          ) : null}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}

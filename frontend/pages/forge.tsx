import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Chip,
  Spinner,
} from '@heroui/react';
import {
  AlertCircle,
  Bot,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  GitPullRequest,
  MessageCircle,
  RefreshCw,
  Terminal,
  Wrench,
  Zap,
} from 'lucide-react';
import PageHeader from '../components/PageHeader';
import { apiFetch } from '../lib/api';
import {
  ForgeMessage,
  ForgeMessageContentBlock,
  ForgeSessionDetail,
  ForgeSessionSummary,
  ForgeSessionsResponse,
} from '../lib/types';

// ==================== 工具函数 ====================

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

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds && seconds !== 0) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = Math.round(seconds - minutes * 60);
  return `${minutes}m${secs.toString().padStart(2, '0')}s`;
}

function formatTokens(value: number | null | undefined): string {
  if (!value) return '—';
  return new Intl.NumberFormat('zh-CN').format(value);
}

function getContentText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((c) => {
        if (typeof c === 'string') return c;
        if (c && typeof c === 'object' && 'text' in c) return String((c as { text: unknown }).text);
        return '';
      })
      .join('\n');
  }
  return JSON.stringify(content, null, 2);
}

// ==================== 状态徽章 ====================

function StatusChip({ status }: { status: string }) {
  if (status === 'completed') {
    return (
      <Chip color="success" variant="flat" size="sm" startContent={<CheckCircle size={13} />}>
        完成
      </Chip>
    );
  }
  if (status === 'failed') {
    return (
      <Chip color="danger" variant="flat" size="sm" startContent={<AlertCircle size={13} />}>
        失败
      </Chip>
    );
  }
  return (
    <Chip color="warning" variant="flat" size="sm" startContent={<Clock size={13} />}>
      运行中
    </Chip>
  );
}

// ==================== 工具调用块 ====================

function ToolUseBlock({ block }: { block: Extract<ForgeMessageContentBlock, { type: 'tool_use' }> }) {
  const [open, setOpen] = useState(false);
  const isTerminal = block.name === 'submit_review' || block.name === 'submit_analysis';
  return (
    <div className={`rounded-md border px-3 py-2 text-sm ${isTerminal ? 'border-green-400 bg-green-50 dark:bg-green-950/30' : 'border-blue-300 bg-blue-50 dark:bg-blue-950/30'}`}>
      <button
        className="flex w-full items-center gap-2 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        {isTerminal ? (
          <CheckCircle size={14} className="shrink-0 text-green-600" />
        ) : (
          <Wrench size={14} className="shrink-0 text-blue-600" />
        )}
        <span className={`font-mono font-semibold ${isTerminal ? 'text-green-700 dark:text-green-400' : 'text-blue-700 dark:text-blue-400'}`}>
          {block.name}
        </span>
        {open ? <ChevronDown size={13} className="ml-auto" /> : <ChevronRight size={13} className="ml-auto" />}
      </button>
      {open && (
        <pre className="mt-2 overflow-x-auto rounded bg-white/60 p-2 text-xs dark:bg-black/20">
          {JSON.stringify(block.input, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ==================== 工具结果块 ====================

function ToolResultBlock({ block }: { block: Extract<ForgeMessageContentBlock, { type: 'tool_result' }> }) {
  const [open, setOpen] = useState(false);
  const text = getContentText(block.content);
  const preview = text.length > 300 ? text.slice(0, 300) + '…' : text;
  const isError = block.is_error;
  return (
    <div className={`rounded-md border px-3 py-2 text-sm ${isError ? 'border-red-300 bg-red-50 dark:bg-red-950/30' : 'border-gray-200 bg-gray-50 dark:bg-gray-800/40'}`}>
      <button
        className="flex w-full items-center gap-2 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        {isError ? (
          <AlertCircle size={14} className="shrink-0 text-red-500" />
        ) : (
          <Terminal size={14} className="shrink-0 text-gray-500" />
        )}
        <span className={`text-xs ${isError ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'}`}>
          工具结果 {isError ? '(错误)' : ''}
        </span>
        {open ? <ChevronDown size={13} className="ml-auto" /> : <ChevronRight size={13} className="ml-auto" />}
      </button>
      <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-xs text-gray-600 dark:text-gray-300">
        {open ? text : preview}
      </pre>
      {!open && text.length > 300 && (
        <button className="mt-1 text-xs text-blue-500 hover:underline" onClick={() => setOpen(true)}>
          显示全部
        </button>
      )}
    </div>
  );
}

// ==================== 单条消息 ====================

function MessageRow({ msg, index }: { msg: ForgeMessage; index: number }) {
  const isAssistant = msg.role === 'assistant';
  const blocks: ForgeMessageContentBlock[] = typeof msg.content === 'string'
    ? [{ type: 'text', text: msg.content }]
    : (msg.content as ForgeMessageContentBlock[]);

  return (
    <div className={`flex gap-3 ${isAssistant ? '' : 'opacity-80'}`}>
      <div className="mt-1 shrink-0">
        {isAssistant ? (
          <Bot size={16} className="text-purple-500" />
        ) : (
          <Terminal size={16} className="text-gray-400" />
        )}
      </div>
      <div className="flex-1 space-y-2">
        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">
          {isAssistant ? `助手 (Turn ${Math.ceil((index + 1) / 2)})` : '工具结果'}
        </div>
        {blocks.map((block, bi) => {
          if (block.type === 'text') {
            return (
              <div key={bi} className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-200">
                {block.text}
              </div>
            );
          }
          if (block.type === 'tool_use') {
            return <ToolUseBlock key={bi} block={block} />;
          }
          if (block.type === 'tool_result') {
            return <ToolResultBlock key={bi} block={block} />;
          }
          return null;
        })}
      </div>
    </div>
  );
}

// ==================== 会话详情展开面板 ====================

function ForgeSessionPanel({ sessionId }: { sessionId: string }) {
  const [detail, setDetail] = useState<ForgeSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch(`/api/forge/sessions/${sessionId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json() as ForgeSessionDetail;
        setDetail(d);
      })
      .catch((e: unknown) => { setError(String(e)); })
      .finally(() => { setLoading(false); });
  }, [sessionId]);

  if (loading) return <div className="flex justify-center py-6"><Spinner size="sm" /></div>;
  if (error) return <div className="py-4 text-sm text-red-500">{error}</div>;
  if (!detail) return null;

  const messages = detail.messages ?? [];

  return (
    <div className="space-y-4 px-2 py-4">
      {messages.length === 0 ? (
        <p className="text-sm text-gray-400">暂无消息记录</p>
      ) : (
        messages.map((msg, i) => <MessageRow key={i} msg={msg} index={i} />)
      )}
    </div>
  );
}

// ==================== 会话列表行 ====================

function SessionRow({ session }: { session: ForgeSessionSummary }) {
  const [expanded, setExpanded] = useState(false);

  const totalTokens = session.input_tokens + session.output_tokens;

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="mt-0.5 shrink-0">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-semibold text-gray-700 dark:text-gray-200">
              {session.session_id}
            </span>
            <StatusChip status={session.status} />
            <Chip
              size="sm"
              variant="flat"
              color={session.scenario === 'review' ? 'primary' : 'secondary'}
            >
              {session.scenario === 'review' ? 'PR 审查' : 'Issue 分析'}
            </Chip>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
            {session.repo_full_name && (
              <span className="truncate">{session.repo_full_name}</span>
            )}
            {session.review_session && (
              <Link
                href={`/reviews?id=${session.review_session.id}`}
                className="flex items-center gap-1 text-blue-500 hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                <GitPullRequest size={12} />
                PR #{session.review_session.pr_number}
                {session.review_session.pr_title ? `: ${session.review_session.pr_title}` : ''}
              </Link>
            )}
            {session.issue_session && (
              <Link
                href={`/issues?id=${session.issue_session.id}`}
                className="flex items-center gap-1 text-purple-500 hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                <MessageCircle size={12} />
                Issue #{session.issue_session.issue_number}
                {session.issue_session.issue_title ? `: ${session.issue_session.issue_title}` : ''}
              </Link>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-400 dark:text-gray-500">
            {session.model && <span>{session.model}</span>}
            <span>{session.turns} 轮</span>
            <span>{session.tool_calls_count} 工具调用</span>
            {totalTokens > 0 && (
              <span className="flex items-center gap-1">
                <Zap size={11} />
                {formatTokens(totalTokens)} tokens
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock size={11} />
              {formatTime(session.started_at)}
            </span>
            {session.duration_seconds != null && (
              <span>{formatDuration(session.duration_seconds)}</span>
            )}
          </div>
          {session.error && (
            <div className="mt-1 text-xs text-red-500 truncate">{session.error}</div>
          )}
        </div>
      </button>
      {expanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30">
          <ForgeSessionPanel sessionId={session.session_id} />
        </div>
      )}
    </div>
  );
}

// ==================== 主页面 ====================

export default function ForgePage() {
  const [sessions, setSessions] = useState<ForgeSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<'all' | 'review' | 'issue'>('all');

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: '100', offset: '0' });
      if (scenario !== 'all') params.set('scenario', scenario);
      const res = await apiFetch(`/api/forge/sessions?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json() as ForgeSessionsResponse;
      setSessions(data.sessions ?? []);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [scenario]);

  useEffect(() => { void fetchSessions(); }, [fetchSessions]);

  return (
    <>
      <Head>
        <title>Forge 会话 - Gitea TLDR</title>
      </Head>
      <PageHeader
        title="Forge 会话"
        icon={<Cpu size={22} />}
        subtitle="查看 Forge agentic loop 的完整思维链与工具调用历史"
      />
      <div className="mx-auto max-w-5xl px-4 py-6 space-y-4">
        {/* 筛选栏 */}
        <div className="flex flex-wrap items-center gap-2">
          {(['all', 'review', 'issue'] as const).map((s) => (
            <Button
              key={s}
              size="sm"
              variant={scenario === s ? 'solid' : 'flat'}
              color={scenario === s ? 'primary' : 'default'}
              onPress={() => setScenario(s)}
            >
              {s === 'all' ? '全部' : s === 'review' ? 'PR 审查' : 'Issue 分析'}
            </Button>
          ))}
          <Button
            size="sm"
            variant="flat"
            isIconOnly
            onPress={() => void fetchSessions()}
            isLoading={loading}
            className="ml-auto"
          >
            <RefreshCw size={15} />
          </Button>
        </div>

        {/* 内容区 */}
        {loading ? (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:bg-red-950/30 dark:border-red-800">
            {error}
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16 text-gray-400">
            <Cpu size={40} className="opacity-30" />
            <p className="text-sm">暂无 Forge 会话记录</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sessions.map((s) => (
              <SessionRow key={s.session_id} session={s} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

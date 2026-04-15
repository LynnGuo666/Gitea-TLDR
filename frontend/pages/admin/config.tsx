import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Checkbox,
  CheckboxGroup,
  Chip,
  Input,
  Select,
  SelectItem,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
  addToast,
} from '@heroui/react';
import { ArrowLeft, ChevronDown, ChevronRight, RefreshCw, Settings2 } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import SectionHeader from '../../components/SectionHeader';
import { apiFetch } from '../../lib/api';

type AdminSetting = {
  key: string;
  value: unknown;
  category: string;
  description: string | null;
  updated_at: string;
};

// 已知有专属控件的 RUNTIME_KEYS
const RUNTIME_KEY_SET = new Set([
  'default_provider',
  'default_review_focus',
  'auto_request_reviewer',
  'bot_username',
  'claude_usage_proxy_enabled',
  'claude_usage_proxy_debug',
  'webhook_log_retention_days',
  'webhook_log_retention_days_failed',
]);

const REVIEW_FOCUS_OPTIONS = ['quality', 'security', 'performance', 'logic'] as const;
const FOCUS_LABELS: Record<string, string> = {
  quality: '代码质量',
  security: '安全',
  performance: '性能',
  logic: '逻辑',
};

function asBoolean(v: unknown, fallback: boolean): boolean {
  return typeof v === 'boolean' ? v : fallback;
}

function asString(v: unknown, fallback: string): string {
  return typeof v === 'string' ? v : fallback;
}

function asNumber(v: unknown, fallback: number): number {
  if (typeof v === 'number') return v;
  const n = Number(v);
  return isNaN(n) ? fallback : n;
}

function asStringArray(v: unknown, fallback: string[]): string[] {
  if (Array.isArray(v)) return v.filter((x): x is string => typeof x === 'string');
  return fallback;
}

function toJsonText(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminConfigPage() {
  const [settingsMap, setSettingsMap] = useState<Map<string, AdminSetting>>(new Map());
  const [otherSettings, setOtherSettings] = useState<AdminSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 审查行为
  const [defaultProvider, setDefaultProvider] = useState('claude_code');
  const [defaultFocus, setDefaultFocus] = useState<string[]>(['quality', 'security', 'performance', 'logic']);
  const [botUsername, setBotUsername] = useState('');
  const [autoRequestReviewer, setAutoRequestReviewer] = useState(true);
  const [reviewSaving, setReviewSaving] = useState(false);

  // Provider 配置（Switch，立即保存）
  const [proxyEnabled, setProxyEnabled] = useState(true);
  const [proxyDebug, setProxyDebug] = useState(false);

  // 日志管理
  const [retentionDays, setRetentionDays] = useState('30');
  const [retentionDaysFailed, setRetentionDaysFailed] = useState('90');
  const [adminSaving, setAdminSaving] = useState(false);

  // 高级区域
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editValueText, setEditValueText] = useState('');
  const [advSaving, setAdvSaving] = useState(false);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/admin/settings');
      if (!res.ok) {
        const msg =
          res.status === 401 || res.status === 403
            ? '当前账号没有配置管理权限'
            : res.status === 503
              ? '数据库未启用，无法读取全局配置'
              : '获取全局配置失败';
        addToast({ title: msg, color: 'danger' });
        return;
      }
      const data = (await res.json()) as AdminSetting[];
      const map = new Map(data.map((s) => [s.key, s]));
      setSettingsMap(map);
      setOtherSettings(data.filter((s) => !RUNTIME_KEY_SET.has(s.key)));

      const dp = map.get('default_provider');
      if (dp) setDefaultProvider(asString(dp.value, 'claude_code'));

      const df = map.get('default_review_focus');
      if (df) setDefaultFocus(asStringArray(df.value, ['quality', 'security', 'performance', 'logic']));

      const bu = map.get('bot_username');
      if (bu) setBotUsername(asString(bu.value, ''));

      const arr = map.get('auto_request_reviewer');
      if (arr) setAutoRequestReviewer(asBoolean(arr.value, true));

      const pe = map.get('claude_usage_proxy_enabled');
      if (pe) setProxyEnabled(asBoolean(pe.value, true));

      const pd = map.get('claude_usage_proxy_debug');
      if (pd) setProxyDebug(asBoolean(pd.value, false));

      const rd = map.get('webhook_log_retention_days');
      if (rd) setRetentionDays(String(asNumber(rd.value, 30)));

      const rdf = map.get('webhook_log_retention_days_failed');
      if (rdf) setRetentionDaysFailed(String(asNumber(rdf.value, 90)));
    } catch {
      addToast({ title: '获取全局配置失败', color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  const putSetting = async (key: string, value: unknown): Promise<boolean> => {
    const existing = settingsMap.get(key);
    const res = await apiFetch(`/api/admin/settings/${encodeURIComponent(key)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        value,
        category: existing?.category ?? 'general',
        description: existing?.description ?? null,
      }),
    });
    return res.ok;
  };

  // Switch 立即保存，失败时回滚
  const saveSwitch = async (key: string, next: boolean, setter: (v: boolean) => void) => {
    setter(next);
    const ok = await putSetting(key, next);
    if (!ok) {
      setter(!next);
      addToast({ title: `保存 ${key} 失败`, color: 'danger' });
    }
  };

  const saveReviewSection = async () => {
    if (defaultFocus.length === 0) {
      addToast({ title: '请至少选择一个审查重点', color: 'warning' });
      return;
    }
    setReviewSaving(true);
    try {
      const results = await Promise.all([
        putSetting('default_provider', defaultProvider),
        putSetting('default_review_focus', defaultFocus),
        putSetting('bot_username', botUsername),
      ]);
      if (results.every(Boolean)) {
        addToast({ title: '审查行为配置已保存', color: 'success' });
        await fetchSettings();
      } else {
        addToast({ title: '部分配置保存失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '保存失败', color: 'danger' });
    } finally {
      setReviewSaving(false);
    }
  };

  const saveAdminSection = async () => {
    const days = parseInt(retentionDays, 10);
    const daysFailed = parseInt(retentionDaysFailed, 10);
    if (!days || days < 1 || !daysFailed || daysFailed < 1) {
      addToast({ title: '保留天数必须为正整数', color: 'warning' });
      return;
    }
    setAdminSaving(true);
    try {
      const results = await Promise.all([
        putSetting('webhook_log_retention_days', days),
        putSetting('webhook_log_retention_days_failed', daysFailed),
      ]);
      if (results.every(Boolean)) {
        addToast({ title: '日志管理配置已保存', color: 'success' });
        await fetchSettings();
      } else {
        addToast({ title: '部分配置保存失败', color: 'danger' });
      }
    } catch {
      addToast({ title: '保存失败', color: 'danger' });
    } finally {
      setAdminSaving(false);
    }
  };

  // 高级区域编辑器
  const startEdit = (setting: AdminSetting) => {
    setEditingKey(setting.key);
    setEditCategory(setting.category || 'general');
    setEditDescription(setting.description || '');
    setEditValueText(toJsonText(setting.value));
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditCategory('');
    setEditDescription('');
    setEditValueText('');
  };

  const saveAdvSetting = async () => {
    if (!editingKey) return;
    let parsedValue: unknown;
    try {
      parsedValue = JSON.parse(editValueText);
    } catch {
      addToast({ title: '配置值必须是合法 JSON', color: 'warning' });
      return;
    }
    setAdvSaving(true);
    try {
      const res = await apiFetch(`/api/admin/settings/${encodeURIComponent(editingKey)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          value: parsedValue,
          category: editCategory || 'general',
          description: editDescription || null,
        }),
      });
      if (!res.ok) {
        addToast({ title: '保存配置失败', color: 'danger' });
        return;
      }
      addToast({ title: `配置 ${editingKey} 已更新`, color: 'success' });
      cancelEdit();
      await fetchSettings();
    } catch {
      addToast({ title: '保存配置失败', color: 'danger' });
    } finally {
      setAdvSaving(false);
    }
  };

  const deleteSetting = async (key: string) => {
    if (!window.confirm(`确认删除配置 ${key} 吗？`)) return;
    setDeletingKey(key);
    try {
      const res = await apiFetch(`/api/admin/settings/${encodeURIComponent(key)}`, { method: 'DELETE' });
      if (!res.ok) {
        addToast({ title: '删除配置失败', color: 'danger' });
        return;
      }
      addToast({ title: `配置 ${key} 已删除`, color: 'success' });
      await fetchSettings();
    } catch {
      addToast({ title: '删除配置失败', color: 'danger' });
    } finally {
      setDeletingKey(null);
    }
  };

  if (loading) {
    return (
      <>
        <Head>
          <title>全局配置 - 管理后台</title>
        </Head>
        <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
          <PageHeader title="全局配置" />
          <div className="py-16 text-center text-default-500">加载配置中...</div>
        </div>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>全局配置 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="全局配置"
          actions={
            <div className="flex items-center gap-2">
              <Button
                isIconOnly
                variant="bordered"
                size="sm"
                onPress={() => fetchSettings()}
                aria-label="刷新配置"
              >
                <RefreshCw size={16} />
              </Button>
              <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
                返回管理后台
              </Button>
            </div>
          }
        />

        {/* 审查行为 */}
        <section className="rounded-xl border border-default-200 p-5 flex flex-col gap-5">
          <SectionHeader title="审查行为" />
          <div className="flex flex-col gap-4">
            <Select
              label="默认审查引擎"
              description={settingsMap.get('default_provider')?.description ?? '触发 PR 审查时默认使用的引擎'}
              selectedKeys={new Set([defaultProvider])}
              onSelectionChange={(keys) => {
                if (keys === 'all') return;
                const k = Array.from(keys)[0];
                if (typeof k === 'string') setDefaultProvider(k);
              }}
              variant="bordered"
            >
              <SelectItem key="claude_code">Claude Code</SelectItem>
              <SelectItem key="codex_cli">Codex CLI</SelectItem>
            </Select>

            <CheckboxGroup
              label="默认审查重点"
              value={defaultFocus}
              onValueChange={setDefaultFocus}
              orientation="horizontal"
              description={settingsMap.get('default_review_focus')?.description ?? '审查时默认关注的维度，至少选一项'}
            >
              {REVIEW_FOCUS_OPTIONS.map((opt) => (
                <Checkbox key={opt} value={opt}>
                  {FOCUS_LABELS[opt]}
                </Checkbox>
              ))}
            </CheckboxGroup>

            <Input
              label="Bot 用户名"
              value={botUsername}
              onValueChange={setBotUsername}
              description={settingsMap.get('bot_username')?.description ?? '用于识别 @ 提及和自动设为审查者'}
              variant="bordered"
              placeholder="例如: review-bot"
            />

            <div className="flex items-center justify-between rounded-lg border border-default-200 px-4 py-3">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">完成后自动设为审查者</span>
                <span className="text-xs text-default-400">
                  {settingsMap.get('auto_request_reviewer')?.description ?? '完成审查后是否自动将 bot 设为 Reviewer'}
                </span>
              </div>
              <Switch
                isSelected={autoRequestReviewer}
                onValueChange={(v) => saveSwitch('auto_request_reviewer', v, setAutoRequestReviewer)}
                aria-label="完成后自动设为审查者"
              />
            </div>
          </div>
          <div className="flex items-center gap-3 pt-1 border-t border-default-100">
            <Button color="primary" size="sm" onPress={saveReviewSection} isLoading={reviewSaving}>
              保存
            </Button>
            <span className="text-xs text-default-400">开关变更立即生效；其余字段点击保存后生效</span>
          </div>
        </section>

        {/* Provider 配置 */}
        <section className="rounded-xl border border-default-200 p-5 flex flex-col gap-3">
          <SectionHeader title="Provider 配置" />
          <p className="text-xs text-default-400 m-0">以下开关变更后立即保存</p>
          <div className="flex flex-col divide-y divide-default-100">
            <div className="flex items-center justify-between py-3">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">启用 Claude Usage 捕获代理</span>
                <span className="text-xs text-default-400">
                  {settingsMap.get('claude_usage_proxy_enabled')?.description ?? '是否启用 Claude usage 捕获代理'}
                </span>
              </div>
              <Switch
                isSelected={proxyEnabled}
                onValueChange={(v) => saveSwitch('claude_usage_proxy_enabled', v, setProxyEnabled)}
                aria-label="启用 Claude Usage 捕获代理"
              />
            </div>
            <div className="flex items-center justify-between py-3">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium">代理诊断日志</span>
                <span className="text-xs text-default-400">
                  {settingsMap.get('claude_usage_proxy_debug')?.description ?? '是否输出 Claude usage 代理诊断日志'}
                </span>
              </div>
              <Switch
                isSelected={proxyDebug}
                onValueChange={(v) => saveSwitch('claude_usage_proxy_debug', v, setProxyDebug)}
                aria-label="代理诊断日志"
              />
            </div>
          </div>
        </section>

        {/* 日志管理 */}
        <section className="rounded-xl border border-default-200 p-5 flex flex-col gap-4">
          <SectionHeader title="日志管理" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              type="number"
              label="成功 Webhook 日志保留天数"
              value={retentionDays}
              onValueChange={setRetentionDays}
              description={settingsMap.get('webhook_log_retention_days')?.description ?? '成功 Webhook 日志的保留天数'}
              variant="bordered"
              min={1}
              endContent={<span className="text-xs text-default-400 whitespace-nowrap self-center">天</span>}
            />
            <Input
              type="number"
              label="失败 Webhook 日志保留天数"
              value={retentionDaysFailed}
              onValueChange={setRetentionDaysFailed}
              description={
                settingsMap.get('webhook_log_retention_days_failed')?.description ?? '失败 Webhook 日志的保留天数'
              }
              variant="bordered"
              min={1}
              endContent={<span className="text-xs text-default-400 whitespace-nowrap self-center">天</span>}
            />
          </div>
          <div className="flex items-center gap-2 pt-1 border-t border-default-100">
            <Button color="primary" size="sm" onPress={saveAdminSection} isLoading={adminSaving}>
              保存
            </Button>
          </div>
        </section>

        {/* 高级：其他非 RUNTIME_KEYS 配置 */}
        {otherSettings.length > 0 ? (
          <section className="rounded-xl border border-default-200">
            <button
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-default-50 transition-colors rounded-xl"
              onClick={() => setShowAdvanced((v) => !v)}
            >
              <div className="flex items-center gap-2">
                <Settings2 size={16} className="text-default-400" />
                <span className="text-sm font-medium">高级配置</span>
                <Chip size="sm" variant="flat">
                  {otherSettings.length}
                </Chip>
              </div>
              {showAdvanced ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>

            {showAdvanced ? (
              <div className="px-5 pb-5 flex flex-col gap-4 border-t border-default-100">
                {editingKey ? (
                  <div className="mt-4 rounded-lg border border-default-200 p-4 flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">编辑: {editingKey}</span>
                      <Chip size="sm" variant="bordered">
                        JSON
                      </Chip>
                    </div>
                    <label className="text-sm text-default-600 flex flex-col gap-1">
                      分类
                      <input
                        className="rounded-md border border-default-200 bg-content1 px-3 py-2 text-sm"
                        value={editCategory}
                        onChange={(e) => setEditCategory(e.target.value)}
                        placeholder="例如: review"
                      />
                    </label>
                    <label className="text-sm text-default-600 flex flex-col gap-1">
                      描述
                      <input
                        className="rounded-md border border-default-200 bg-content1 px-3 py-2 text-sm"
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        placeholder="配置说明"
                      />
                    </label>
                    <label className="text-sm text-default-600 flex flex-col gap-1">
                      值（JSON）
                      <textarea
                        className="rounded-md border border-default-200 bg-content1 px-3 py-2 min-h-36 font-mono text-xs"
                        value={editValueText}
                        onChange={(e) => setEditValueText(e.target.value)}
                      />
                    </label>
                    <div className="flex items-center gap-2">
                      <Button color="primary" size="sm" onPress={saveAdvSetting} isLoading={advSaving}>
                        保存
                      </Button>
                      <Button variant="bordered" size="sm" onPress={cancelEdit} isDisabled={advSaving}>
                        取消
                      </Button>
                    </div>
                  </div>
                ) : null}

                <div className="rounded-lg border border-default-200 overflow-hidden mt-2">
                  <Table aria-label="其他配置" removeWrapper>
                    <TableHeader>
                      <TableColumn>KEY</TableColumn>
                      <TableColumn>分类</TableColumn>
                      <TableColumn>值</TableColumn>
                      <TableColumn>更新时间</TableColumn>
                      <TableColumn>操作</TableColumn>
                    </TableHeader>
                    <TableBody>
                      {otherSettings.map((s) => (
                        <TableRow key={s.key}>
                          <TableCell>
                            <div className="text-sm font-medium">{s.key}</div>
                            <div className="text-xs text-default-400">{s.description ?? '无描述'}</div>
                          </TableCell>
                          <TableCell>
                            <Chip size="sm" variant="flat">
                              {s.category || 'general'}
                            </Chip>
                          </TableCell>
                          <TableCell>
                            <pre className="m-0 text-xs whitespace-pre-wrap max-w-[300px] line-clamp-3">
                              {toJsonText(s.value)}
                            </pre>
                          </TableCell>
                          <TableCell>{formatTime(s.updated_at)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Button size="sm" variant="bordered" onPress={() => startEdit(s)}>
                                编辑
                              </Button>
                              <Button
                                size="sm"
                                color="danger"
                                variant="light"
                                isLoading={deletingKey === s.key}
                                onPress={() => deleteSetting(s.key)}
                              >
                                删除
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </>
  );
}

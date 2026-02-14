import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
} from '@heroui/react';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';

type AdminSetting = {
  key: string;
  value: unknown;
  category: string;
  description: string | null;
  updated_at: string;
};

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function toJsonText(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export default function AdminConfigPage() {
  const [settings, setSettings] = useState<AdminSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [filterCategory, setFilterCategory] = useState('all');
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editValueText, setEditValueText] = useState('');

  const fetchSettings = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const query = filterCategory === 'all' ? '' : `?category=${encodeURIComponent(filterCategory)}`;
      const res = await apiFetch(`/api/admin/settings${query}`);
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          throw new Error('当前账号没有配置管理权限');
        }
        if (res.status === 503) {
          throw new Error('数据库未启用，无法读取全局配置');
        }
        throw new Error('获取全局配置失败');
      }
      const data = (await res.json()) as AdminSetting[];
      setSettings(data);
    } catch (err) {
      setSettings([]);
      setError(err instanceof Error ? err.message : '获取全局配置失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filterCategory]);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  const categoryOptions = useMemo(() => {
    const categories = new Set(settings.map((item) => item.category).filter(Boolean));
    return ['all', ...Array.from(categories).sort()];
  }, [settings]);

  const startEdit = (setting: AdminSetting) => {
    setEditingKey(setting.key);
    setEditCategory(setting.category || 'general');
    setEditDescription(setting.description || '');
    setEditValueText(toJsonText(setting.value));
    setMessage(null);
    setError(null);
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditCategory('');
    setEditDescription('');
    setEditValueText('');
  };

  const saveSetting = async () => {
    if (!editingKey) return;

    let parsedValue: unknown;
    try {
      parsedValue = JSON.parse(editValueText);
    } catch {
      setError('配置值必须是合法 JSON');
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);
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
        const detail = await res.text();
        throw new Error(detail || '保存配置失败');
      }

      setMessage(`配置 ${editingKey} 已更新`);
      cancelEdit();
      await fetchSettings(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  const deleteSetting = async (key: string) => {
    if (!window.confirm(`确认删除配置 ${key} 吗？`)) {
      return;
    }

    setDeletingKey(key);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch(`/api/admin/settings/${encodeURIComponent(key)}`, { method: 'DELETE' });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || '删除配置失败');
      }
      setMessage(`配置 ${key} 已删除`);
      await fetchSettings(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除配置失败');
    } finally {
      setDeletingKey(null);
    }
  };

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
                onPress={() => fetchSettings(true)}
                isDisabled={refreshing || loading}
                aria-label="刷新配置"
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
        {message ? <div className="rounded-lg border border-success-200 bg-success-50 p-3 text-success-700 text-sm">{message}</div> : null}

        {editingKey ? (
          <section className="rounded-lg border border-default-200 p-4 sm:p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="m-0 text-base font-semibold">编辑配置: {editingKey}</h2>
              <Chip size="sm" variant="bordered">JSON</Chip>
            </div>
            <label className="text-sm text-default-600 flex flex-col gap-1">
              分类
              <input
                className="rounded-md border border-default-200 bg-content1 px-3 py-2"
                value={editCategory}
                onChange={(e) => setEditCategory(e.target.value)}
                placeholder="例如: review"
              />
            </label>
            <label className="text-sm text-default-600 flex flex-col gap-1">
              描述
              <input
                className="rounded-md border border-default-200 bg-content1 px-3 py-2"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="配置说明"
              />
            </label>
            <label className="text-sm text-default-600 flex flex-col gap-1">
              值（JSON）
              <textarea
                className="rounded-md border border-default-200 bg-content1 px-3 py-2 min-h-40 font-mono text-xs"
                value={editValueText}
                onChange={(e) => setEditValueText(e.target.value)}
              />
            </label>
            <div className="flex items-center gap-2">
              <Button color="primary" onPress={saveSetting} isLoading={saving}>保存</Button>
              <Button variant="bordered" onPress={cancelEdit} isDisabled={saving}>取消</Button>
            </div>
          </section>
        ) : null}

        <section className="rounded-lg border border-default-200 p-4 sm:p-5 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="m-0 text-sm text-default-500">共 {settings.length} 条配置项</p>
            <label className="text-sm text-default-500 inline-flex items-center gap-2">
              分类过滤
              <select
                className="rounded-md border border-default-200 bg-content1 px-2 py-1"
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
              >
                {categoryOptions.map((category) => (
                  <option key={category} value={category}>
                    {category === 'all' ? '全部' : category}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {loading ? (
            <div className="py-10 text-center text-default-500">加载配置中...</div>
          ) : settings.length === 0 ? (
            <div className="py-10 text-center text-default-500">暂无配置数据</div>
          ) : (
            <div className="rounded-lg border border-default-200 overflow-hidden">
              <Table aria-label="全局配置表" removeWrapper>
                <TableHeader>
                  <TableColumn>KEY</TableColumn>
                  <TableColumn>分类</TableColumn>
                  <TableColumn>值</TableColumn>
                  <TableColumn>更新时间</TableColumn>
                  <TableColumn>操作</TableColumn>
                </TableHeader>
                <TableBody>
                  {settings.map((setting) => (
                    <TableRow key={setting.key}>
                      <TableCell>
                        <div className="text-sm font-medium">{setting.key}</div>
                        <div className="text-xs text-default-400">{setting.description || '无描述'}</div>
                      </TableCell>
                      <TableCell>
                        <Chip size="sm" variant="flat">{setting.category || 'general'}</Chip>
                      </TableCell>
                      <TableCell>
                        <pre className="m-0 text-xs whitespace-pre-wrap max-w-[360px] line-clamp-4">{toJsonText(setting.value)}</pre>
                      </TableCell>
                      <TableCell>{formatTime(setting.updated_at)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button size="sm" variant="bordered" onPress={() => startEdit(setting)}>编辑</Button>
                          <Button
                            size="sm"
                            color="danger"
                            variant="light"
                            isLoading={deletingKey === setting.key}
                            onPress={() => deleteSetting(setting.key)}
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
          )}
        </section>
      </div>
    </>
  );
}

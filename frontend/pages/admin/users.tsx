import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Checkbox,
  CheckboxGroup,
  Chip,
  Input,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Select,
  SelectItem,
  Spinner,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableColumn,
  TableHeader,
  TableRow,
  useDisclosure,
} from '@heroui/react';
import { ArrowLeft, RefreshCw, Plus } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { apiFetch } from '../../lib/api';
import { fetchAdminStatus } from '../../lib/auth';

type AdminUserItem = {
  username: string;
  email: string | null;
  role: 'super_admin' | 'admin';
  permissions: Record<string, string[]> | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

type FormState = {
  username: string;
  email: string;
  role: 'super_admin' | 'admin';
  permissions: Record<string, string[]>;
  is_active: boolean;
};

const PERMISSION_RESOURCES: { key: string; label: string; actions: string[] }[] = [
  { key: 'users', label: '用户管理', actions: ['read', 'write', 'delete'] },
  { key: 'config', label: '全局配置', actions: ['read', 'write', 'delete'] },
  { key: 'webhooks', label: 'Webhook', actions: ['read'] },
];

const DEFAULT_FORM: FormState = {
  username: '',
  email: '',
  role: 'admin',
  permissions: {},
  is_active: true,
};

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);

  const [editingUser, setEditingUser] = useState<AdminUserItem | null>(null);
  const [deletingUser, setDeletingUser] = useState<AdminUserItem | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);

  const editModal = useDisclosure();
  const deleteModal = useDisclosure();

  const fetchUsers = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const res = await apiFetch('/api/admin/users');
      if (!res.ok) {
        if (res.status === 403) {
          setError('当前账号没有用户管理权限（需要 super_admin）');
          return;
        }
        if (res.status === 503) {
          throw new Error('数据库未启用');
        }
        throw new Error('获取用户列表失败');
      }
      const data = (await res.json()) as AdminUserItem[];
      setUsers(data);
    } catch (err) {
      setUsers([]);
      setError(err instanceof Error ? err.message : '获取用户列表失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchUsers();
    fetchAdminStatus()
      .then((s) => setIsSuperAdmin(s.role === 'super_admin'))
      .catch(() => setIsSuperAdmin(false));
  }, [fetchUsers]);

  const openCreate = () => {
    setEditingUser(null);
    setForm(DEFAULT_FORM);
    setMessage(null);
    setError(null);
    editModal.onOpen();
  };

  const openEdit = (user: AdminUserItem) => {
    setEditingUser(user);
    setForm({
      username: user.username,
      email: user.email ?? '',
      role: user.role,
      permissions: user.permissions ?? {},
      is_active: user.is_active,
    });
    setMessage(null);
    setError(null);
    editModal.onOpen();
  };

  const openDelete = (user: AdminUserItem) => {
    setDeletingUser(user);
    deleteModal.onOpen();
  };

  const setPermActions = (resource: string, actions: string[]) => {
    setForm((prev) => ({
      ...prev,
      permissions: { ...prev.permissions, [resource]: actions },
    }));
  };

  const saveUser = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const isCreate = editingUser === null;
      const body = isCreate
        ? {
            username: form.username,
            email: form.email || null,
            role: form.role,
            permissions: form.role === 'admin' ? form.permissions : null,
          }
        : {
            email: form.email || null,
            role: form.role,
            permissions: form.role === 'admin' ? form.permissions : null,
            is_active: form.is_active,
          };

      const url = isCreate
        ? '/api/admin/users'
        : `/api/admin/users/${encodeURIComponent(editingUser.username)}`;
      const method = isCreate ? 'POST' : 'PUT';

      const res = await apiFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || (isCreate ? '创建用户失败' : '更新用户失败'));
      }

      setMessage(isCreate ? `用户 ${form.username} 已创建` : `用户 ${editingUser.username} 已更新`);
      editModal.onClose();
      await fetchUsers(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (user: AdminUserItem) => {
    try {
      const res = await apiFetch(`/api/admin/users/${encodeURIComponent(user.username)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !user.is_active }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || '操作失败');
      }
      await fetchUsers(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  const confirmDelete = async () => {
    if (!deletingUser) return;
    setDeleting(true);
    try {
      const res = await apiFetch(`/api/admin/users/${encodeURIComponent(deletingUser.username)}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || '删除失败');
      }
      setMessage(`用户 ${deletingUser.username} 已删除`);
      deleteModal.onClose();
      await fetchUsers(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Head>
        <title>用户管理 - 管理后台</title>
      </Head>
      <div className="max-w-[1100px] mx-auto flex flex-col gap-5">
        <PageHeader
          title="用户管理"
          actions={
            <div className="flex items-center gap-2">
              <Button
                isIconOnly
                variant="bordered"
                size="sm"
                onPress={() => fetchUsers(true)}
                isDisabled={refreshing || loading}
                aria-label="刷新用户列表"
              >
                <RefreshCw size={16} className={refreshing || loading ? 'animate-spin' : ''} />
              </Button>
              {isSuperAdmin && (
                <Button color="primary" size="sm" startContent={<Plus size={16} />} onPress={openCreate}>
                  新建用户
                </Button>
              )}
              <Button as={Link} href="/admin" variant="bordered" size="sm" startContent={<ArrowLeft size={16} />}>
                返回管理后台
              </Button>
            </div>
          }
        />

        {!isSuperAdmin && !loading && (
          <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-warning-700 text-sm">
            当前账号角色不是 super_admin，部分操作（新建、删除、修改角色）不可用。
          </div>
        )}
        {error && (
          <div className="rounded-lg border border-danger-200 bg-danger-50 p-3 text-danger-700 text-sm">{error}</div>
        )}
        {message && (
          <div className="rounded-lg border border-success-200 bg-success-50 p-3 text-success-700 text-sm">{message}</div>
        )}

        <section className="rounded-lg border border-default-200 p-4 sm:p-5 flex flex-col gap-4">
          {loading ? (
            <div className="py-10 flex justify-center">
              <Spinner label="加载用户列表中..." />
            </div>
          ) : users.length === 0 ? (
            <div className="py-10 text-center text-default-500">暂无用户数据</div>
          ) : (
            <div className="rounded-lg border border-default-200 overflow-hidden">
              <Table aria-label="管理员用户表" removeWrapper>
                <TableHeader>
                  <TableColumn>用户名</TableColumn>
                  <TableColumn>邮箱</TableColumn>
                  <TableColumn>角色</TableColumn>
                  <TableColumn>状态</TableColumn>
                  <TableColumn>最后登录</TableColumn>
                  <TableColumn>操作</TableColumn>
                </TableHeader>
                <TableBody>
                  {users.map((user) => (
                    <TableRow key={user.username}>
                      <TableCell>
                        <div className="font-medium">{user.username}</div>
                        <div className="text-xs text-default-400">{formatTime(user.created_at)} 创建</div>
                      </TableCell>
                      <TableCell>{user.email ?? '—'}</TableCell>
                      <TableCell>
                        <Chip
                          size="sm"
                          variant="flat"
                          color={user.role === 'super_admin' ? 'warning' : 'primary'}
                        >
                          {user.role === 'super_admin' ? '超级管理员' : '管理员'}
                        </Chip>
                      </TableCell>
                      <TableCell>
                        <Switch
                          size="sm"
                          isSelected={user.is_active}
                          onValueChange={() => toggleActive(user)}
                          aria-label={user.is_active ? '已启用' : '已停用'}
                        />
                      </TableCell>
                      <TableCell>{formatTime(user.last_login_at)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button size="sm" variant="bordered" onPress={() => openEdit(user)}>
                            编辑
                          </Button>
                          {isSuperAdmin && (
                            <Button
                              size="sm"
                              color="danger"
                              variant="light"
                              onPress={() => openDelete(user)}
                            >
                              删除
                            </Button>
                          )}
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

      {/* 新建/编辑 Modal */}
      <Modal isOpen={editModal.isOpen} onClose={editModal.onClose} size="lg">
        <ModalContent>
          <ModalHeader>{editingUser ? `编辑用户：${editingUser.username}` : '新建用户'}</ModalHeader>
          <ModalBody className="flex flex-col gap-4">
            {error && (
              <div className="rounded-lg border border-danger-200 bg-danger-50 p-2 text-danger-700 text-sm">{error}</div>
            )}
            <Input
              label="用户名"
              value={form.username}
              onValueChange={(v) => setForm((p) => ({ ...p, username: v }))}
              isDisabled={editingUser !== null}
              isRequired
            />
            <Input
              label="邮箱"
              value={form.email}
              onValueChange={(v) => setForm((p) => ({ ...p, email: v }))}
              type="email"
            />
            <Select
              label="角色"
              selectedKeys={[form.role]}
              onSelectionChange={(keys) => {
                const role = Array.from(keys)[0] as 'super_admin' | 'admin';
                setForm((p) => ({ ...p, role }));
              }}
              isDisabled={!isSuperAdmin}
            >
              <SelectItem key="admin">管理员</SelectItem>
              <SelectItem key="super_admin">超级管理员</SelectItem>
            </Select>

            {form.role === 'admin' && (
              <div className="flex flex-col gap-3">
                <p className="text-sm font-medium text-default-600">权限配置</p>
                {PERMISSION_RESOURCES.map(({ key, label, actions }) => (
                  <div key={key} className="rounded-lg border border-default-200 p-3">
                    <p className="text-xs font-semibold text-default-500 mb-2">{label}</p>
                    <CheckboxGroup
                      orientation="horizontal"
                      value={form.permissions[key] ?? []}
                      onValueChange={(vals) => setPermActions(key, vals)}
                    >
                      {actions.map((action) => (
                        <Checkbox key={action} value={action}>
                          {action}
                        </Checkbox>
                      ))}
                    </CheckboxGroup>
                  </div>
                ))}
              </div>
            )}

            {editingUser && (
              <div className="flex items-center gap-3">
                <Switch
                  isSelected={form.is_active}
                  onValueChange={(v) => setForm((p) => ({ ...p, is_active: v }))}
                  size="sm"
                />
                <span className="text-sm text-default-600">账号启用</span>
              </div>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="bordered" onPress={editModal.onClose} isDisabled={saving}>
              取消
            </Button>
            <Button color="primary" onPress={saveUser} isLoading={saving}>
              保存
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* 删除确认 Modal */}
      <Modal isOpen={deleteModal.isOpen} onClose={deleteModal.onClose}>
        <ModalContent>
          <ModalHeader>确认删除</ModalHeader>
          <ModalBody>
            <p className="text-sm">
              确定要删除管理员 <strong>{deletingUser?.username}</strong> 吗？此操作不可撤销。
            </p>
          </ModalBody>
          <ModalFooter>
            <Button variant="bordered" onPress={deleteModal.onClose} isDisabled={deleting}>
              取消
            </Button>
            <Button color="danger" onPress={confirmDelete} isLoading={deleting}>
              删除
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
}

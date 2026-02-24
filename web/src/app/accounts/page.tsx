'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus,
  Pencil,
  Trash2,
  Shield,
  User as UserIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { useAuthStore } from '@/stores/auth-store';
import { authApi } from '@/lib/api';
import { useTranslation } from '@/i18n/client';
import { formatDateTime } from '@/lib/formatters';
import { toast } from 'sonner';

interface UserInfo {
  id: string;
  username: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

export default function AccountsPage() {
  const router = useRouter();
  const { user: currentUser } = useAuthStore();
  const { t } = useTranslation('auth');
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Add/Edit dialog
  const [showDialog, setShowDialog] = useState(false);
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null);
  const [formUsername, setFormUsername] = useState('');
  const [formPassword, setFormPassword] = useState('');
  const [formDisplayName, setFormDisplayName] = useState('');
  const [formRole, setFormRole] = useState('user');
  const [formActive, setFormActive] = useState(true);
  const [saving, setSaving] = useState(false);

  // Delete dialog
  const [deleteUser, setDeleteUser] = useState<UserInfo | null>(null);

  const fetchUsers = useCallback(async () => {
    try {
      const data = await authApi.listUsers();
      setUsers(data);
    } catch {
      toast.error(t('accounts.fetchFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    // Redirect non-admins
    if (currentUser && currentUser.role !== 'admin') {
      router.replace('/');
      return;
    }
    fetchUsers();
  }, [currentUser, router, fetchUsers]);

  function openAddDialog() {
    setEditingUser(null);
    setFormUsername('');
    setFormPassword('');
    setFormDisplayName('');
    setFormRole('user');
    setFormActive(true);
    setShowDialog(true);
  }

  function openEditDialog(user: UserInfo) {
    setEditingUser(user);
    setFormUsername(user.username);
    setFormPassword('');
    setFormDisplayName(user.display_name || '');
    setFormRole(user.role);
    setFormActive(user.is_active);
    setShowDialog(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);

    try {
      if (editingUser) {
        // Update
        const updates: Record<string, unknown> = {};
        if (formDisplayName !== (editingUser.display_name || '')) updates.display_name = formDisplayName;
        if (formRole !== editingUser.role) updates.role = formRole;
        if (formActive !== editingUser.is_active) updates.is_active = formActive;
        if (formPassword) updates.password = formPassword;
        await authApi.updateUser(editingUser.id, updates);
        toast.success(t('accounts.userUpdated'));
      } else {
        // Create
        await authApi.createUser({
          username: formUsername,
          password: formPassword,
          display_name: formDisplayName || undefined,
          role: formRole,
        });
        toast.success(t('accounts.userCreated'));
      }
      setShowDialog(false);
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('accounts.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteUser) return;
    try {
      await authApi.deleteUser(deleteUser.id);
      toast.success(t('accounts.userDeleted'));
      setDeleteUser(null);
      fetchUsers();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('accounts.deleteFailed'));
    }
  }

  const isSelf = (userId: string) => currentUser?.id === userId;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="container max-w-4xl py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">{t('accounts.title')}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t('accounts.description')}</p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="h-4 w-4 mr-2" />
          {t('accounts.addUser')}
        </Button>
      </div>

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3 text-sm font-medium">{t('accounts.username')}</th>
              <th className="text-left p-3 text-sm font-medium">{t('accounts.displayName')}</th>
              <th className="text-left p-3 text-sm font-medium">{t('accounts.role')}</th>
              <th className="text-left p-3 text-sm font-medium">{t('accounts.status')}</th>
              <th className="text-left p-3 text-sm font-medium">{t('accounts.createdAt')}</th>
              <th className="text-right p-3 text-sm font-medium">{t('accounts.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="p-3 text-sm font-medium">
                  {u.username}
                  {isSelf(u.id) && (
                    <Badge variant="outline" className="ml-2 text-xs">{t('accounts.you')}</Badge>
                  )}
                </td>
                <td className="p-3 text-sm text-muted-foreground">{u.display_name || '—'}</td>
                <td className="p-3">
                  <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>
                    {u.role === 'admin' ? (
                      <><Shield className="h-3 w-3 mr-1" />{t('accounts.admin')}</>
                    ) : (
                      <><UserIcon className="h-3 w-3 mr-1" />{t('accounts.user')}</>
                    )}
                  </Badge>
                </td>
                <td className="p-3">
                  <Badge variant={u.is_active ? 'success' : 'destructive'}>
                    {u.is_active ? t('accounts.active') : t('accounts.inactive')}
                  </Badge>
                </td>
                <td className="p-3 text-sm text-muted-foreground">
                  {u.created_at ? formatDateTime(u.created_at) : '—'}
                </td>
                <td className="p-3 text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button variant="ghost" size="icon" onClick={() => openEditDialog(u)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteUser(u)}
                      disabled={isSelf(u.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingUser ? t('accounts.editUser') : t('accounts.addUser')}</DialogTitle>
            <DialogDescription>
              {editingUser ? t('accounts.editUserDescription') : t('accounts.addUserDescription')}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSave} className="space-y-4">
            {!editingUser && (
              <div className="space-y-2">
                <Label htmlFor="form-username">{t('accounts.username')}</Label>
                <Input
                  id="form-username"
                  value={formUsername}
                  onChange={(e) => setFormUsername(e.target.value)}
                  required
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="form-password">
                {editingUser ? t('accounts.newPassword') : t('accounts.password')}
              </Label>
              <Input
                id="form-password"
                type="password"
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                required={!editingUser}
                placeholder={editingUser ? t('accounts.leaveBlank') : undefined}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="form-display-name">{t('accounts.displayName')}</Label>
              <Input
                id="form-display-name"
                value={formDisplayName}
                onChange={(e) => setFormDisplayName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>{t('accounts.role')}</Label>
              <Select
                value={formRole}
                onValueChange={setFormRole}
                disabled={editingUser ? isSelf(editingUser.id) : false}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">{t('accounts.admin')}</SelectItem>
                  <SelectItem value="user">{t('accounts.user')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {editingUser && !isSelf(editingUser.id) && (
              <div className="flex items-center justify-between">
                <Label htmlFor="form-active">{t('accounts.activeToggle')}</Label>
                <Switch
                  id="form-active"
                  checked={formActive}
                  onCheckedChange={setFormActive}
                />
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowDialog(false)}>
                {t('user.cancel')}
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? t('accounts.saving') : (editingUser ? t('accounts.save') : t('accounts.create'))}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteUser} onOpenChange={() => setDeleteUser(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('accounts.deleteUser')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('accounts.confirmDelete', { username: deleteUser?.username })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('user.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('accounts.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

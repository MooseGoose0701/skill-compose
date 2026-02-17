'use client';

import { useState, useRef, useCallback } from 'react';
import {
  Archive,
  Download,
  Upload,
  RotateCcw,
  Shield,
  HardDrive,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from '@/i18n/client';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogCancel,
  AlertDialogAction,
} from '@/components/ui/alert-dialog';
import { useBackupList, useCreateBackup, useRestoreFromUpload, useRestoreFromServer } from '@/hooks/use-backup';
import { backupApi } from '@/lib/api';
import type { RestoreResponse } from '@/lib/api';
import { formatDateTime, formatFileSize } from '@/lib/formatters';

export default function BackupPage() {
  const { t } = useTranslation('backup');
  const { t: tc } = useTranslation('common');

  const [includeEnv, setIncludeEnv] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmFilename, setConfirmFilename] = useState<string | null>(null);
  const [restoreResult, setRestoreResult] = useState<RestoreResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: backupList, isLoading: listLoading, error: listError } = useBackupList();
  const createBackup = useCreateBackup();
  const restoreFromUpload = useRestoreFromUpload();
  const restoreFromServer = useRestoreFromServer();

  const isRestoring = restoreFromUpload.isPending || restoreFromServer.isPending;

  const handleCreateBackup = async () => {
    try {
      const blob = await createBackup.mutateAsync({ includeEnv });
      // Auto-download
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backup_${new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(t('create.success'));
    } catch (err) {
      toast.error(`${t('create.error')}: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleFileSelect = (file: File) => {
    if (!file.name.endsWith('.zip')) {
      toast.error(t('restore.invalidFileType'));
      return;
    }
    setSelectedFile(file);
    setRestoreResult(null);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const openUploadConfirm = () => {
    if (!selectedFile) return;
    setConfirmFilename(null);
    setConfirmOpen(true);
  };

  const openServerConfirm = (filename: string) => {
    setConfirmFilename(filename);
    setConfirmOpen(true);
  };

  const handleConfirmRestore = async () => {
    setConfirmOpen(false);
    setRestoreResult(null);
    try {
      let result: RestoreResponse;
      if (confirmFilename) {
        result = await restoreFromServer.mutateAsync(confirmFilename);
      } else if (selectedFile) {
        result = await restoreFromUpload.mutateAsync(selectedFile);
      } else {
        return;
      }
      setRestoreResult(result);
      toast.success(t('restore.success'));
    } catch (err) {
      toast.error(`${t('restore.error')}: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Archive className="h-8 w-8" />
          {t('title')}
        </h1>
        <p className="mt-2 text-muted-foreground">{t('description')}</p>
      </div>

      <div className="space-y-6">
        {/* Create Backup Card */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-start gap-3 mb-4">
            <HardDrive className="h-5 w-5 mt-0.5 text-primary" />
            <div className="flex-1">
              <h2 className="text-lg font-semibold">{t('create.title')}</h2>
              <p className="text-sm text-muted-foreground mt-1">{t('create.description')}</p>
            </div>
          </div>

          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={includeEnv}
                onChange={(e) => setIncludeEnv(e.target.checked)}
                className="rounded border-gray-300"
              />
              <span>{t('create.includeEnv')}</span>
            </label>
            {includeEnv && (
              <div className="flex items-start gap-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/30 rounded-md p-2.5">
                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                <span>{t('create.includeEnvWarning')}</span>
              </div>
            )}

            <Button
              onClick={handleCreateBackup}
              disabled={createBackup.isPending}
              className="w-full sm:w-auto"
            >
              {createBackup.isPending ? (
                <>
                  <Spinner size="sm" className="mr-2" />
                  {t('create.creating')}
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  {t('create.button')}
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Restore from Backup Card */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-start gap-3 mb-4">
            <Upload className="h-5 w-5 mt-0.5 text-primary" />
            <div className="flex-1">
              <h2 className="text-lg font-semibold">{t('restore.title')}</h2>
              <p className="text-sm text-muted-foreground mt-1">{t('restore.description')}</p>
            </div>
          </div>

          {/* Drop zone */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer ${
              dragOver
                ? 'border-primary bg-primary/5 scale-[1.01] shadow-sm'
                : 'border-muted-foreground/30 hover:border-primary/50 hover:bg-muted/30'
            }`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => !selectedFile && fileInputRef.current?.click()}
          >
            <div className={`mx-auto mb-3 w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
              dragOver ? 'bg-primary/10' : 'bg-muted'
            }`}>
              <Upload className={`h-6 w-6 transition-colors ${dragOver ? 'text-primary' : 'text-muted-foreground'}`} />
            </div>
            <p className="text-sm font-medium mb-1">{t('restore.dragDrop')}</p>
            <p className="text-xs text-muted-foreground mb-3">{t('restore.orClickToBrowse')}</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileSelect(file);
              }}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
            >
              {t('restore.selectFile')}
            </Button>

            {selectedFile && (
              <div className="mt-3 text-sm">
                <Badge variant="secondary">{selectedFile.name}</Badge>
                <span className="ml-2 text-muted-foreground">
                  ({formatFileSize(selectedFile.size)})
                </span>
              </div>
            )}
          </div>

          {selectedFile && (
            <div className="mt-4">
              <Button
                onClick={openUploadConfirm}
                disabled={isRestoring}
                variant="destructive"
              >
                {isRestoring && !confirmFilename ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    {t('restore.restoring')}
                  </>
                ) : (
                  <>
                    <RotateCcw className="mr-2 h-4 w-4" />
                    {t('restore.button')}
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Restore result */}
          {restoreResult && (
            <div className="mt-4 rounded-md border p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-green-600 dark:text-green-400">
                <CheckCircle className="h-4 w-4" />
                {t('restore.success')}
              </div>
              {restoreResult.snapshot_filename && (
                <p className="text-xs text-muted-foreground">
                  <Shield className="inline h-3 w-3 mr-1" />
                  {t('restore.snapshot')} <code className="text-xs">{restoreResult.snapshot_filename}</code>
                </p>
              )}
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge variant="outline">{t('stats.skills')}: {restoreResult.restored.skills}</Badge>
                <Badge variant="outline">{t('stats.agents')}: {restoreResult.restored.agent_presets}</Badge>
                <Badge variant="outline">{t('stats.traces')}: {restoreResult.restored.agent_traces}</Badge>
                <Badge variant="outline">{t('stats.sessions')}: {restoreResult.restored.published_sessions}</Badge>
              </div>
              {restoreResult.errors.length > 0 && (
                <div className="mt-2">
                  <ErrorBanner
                    title={t('errors.warnings', { count: restoreResult.errors.length })}
                    message={restoreResult.errors.join('\n')}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Available Backups Card */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-start gap-3 mb-4">
            <Archive className="h-5 w-5 mt-0.5 text-primary" />
            <div className="flex-1">
              <h2 className="text-lg font-semibold">{t('list.title')}</h2>
            </div>
          </div>

          {listError && (
            <ErrorBanner message={listError instanceof Error ? listError.message : t('errors.loadFailed')} />
          )}

          {listLoading && (
            <div className="flex items-center justify-center py-8">
              <Spinner size="md" />
            </div>
          )}

          {!listLoading && !listError && backupList && backupList.backups.length === 0 && (
            <EmptyState
              icon={Archive}
              title={t('list.empty')}
              description={t('list.emptyDescription')}
            />
          )}

          {!listLoading && backupList && backupList.backups.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">{t('list.filename')}</th>
                    <th className="pb-2 font-medium">{t('list.size')}</th>
                    <th className="pb-2 font-medium">{t('list.createdAt')}</th>
                    <th className="pb-2 font-medium text-right"></th>
                  </tr>
                </thead>
                <tbody>
                  {backupList.backups.map((backup) => (
                    <tr key={backup.filename} className="border-b last:border-0">
                      <td className="py-3">
                        <div>
                          <span className="font-mono text-xs">{backup.filename}</span>
                          {backup.stats && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                {t('stats.skills')}: {backup.stats.skills}
                              </Badge>
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                {t('stats.agents')}: {backup.stats.agent_presets}
                              </Badge>
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                {t('stats.traces')}: {backup.stats.agent_traces}
                              </Badge>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {formatFileSize(backup.size_bytes)}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {formatDateTime(backup.created_at)}
                      </td>
                      <td className="py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <a
                            href={backupApi.getDownloadUrl(backup.filename)}
                            className="inline-flex items-center justify-center rounded-md text-sm font-medium h-8 px-3 border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground transition-colors"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openServerConfirm(backup.filename)}
                            disabled={isRestoring}
                          >
                            {isRestoring && confirmFilename === backup.filename ? (
                              <Spinner size="sm" />
                            ) : (
                              <RotateCcw className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Confirm Restore Dialog */}
      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              {t('restore.confirmTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <div className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-sm font-semibold text-destructive dark:text-red-400 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                  {t('restore.confirmWarning')}
                </div>
                <p className="text-sm text-muted-foreground">{t('restore.confirmMessage')}</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmRestore}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {t('restore.confirmButton')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Clock, Plus, Trash2, Pause, Play, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import { Spinner } from '@/components/ui/spinner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  useScheduledTasks,
  useDeleteScheduledTask,
  usePauseTask,
  useResumeTask,
  useRunTaskNow,
} from '@/hooks/use-scheduled-tasks';
import { useTranslation } from '@/i18n/client';
import { formatDateTime } from '@/lib/formatters';
import type { ScheduledTask } from '@/lib/api';

const STATUS_OPTIONS = ['active', 'paused', 'completed'] as const;

function StatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, 'success' | 'warning' | 'secondary'> = {
    active: 'success',
    paused: 'warning',
    completed: 'secondary',
  };
  return <Badge variant={variantMap[status] || 'secondary'}>{status}</Badge>;
}

export default function ScheduledTasksPage() {
  const { t } = useTranslation('scheduled-tasks');
  const { t: tc } = useTranslation('common');

  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  const { data: tasks, isLoading, error } = useScheduledTasks(
    statusFilter ? { status: statusFilter } : undefined
  );
  const deleteTask = useDeleteScheduledTask();
  const pauseTask = usePauseTask();
  const resumeTask = useResumeTask();
  const runTaskNow = useRunTaskNow();

  const taskList = useMemo(() => tasks || [], [tasks]);

  const handleDelete = async (id: string) => {
    try {
      await deleteTask.mutateAsync(id);
      toast.success(t('messages.deleted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handlePause = async (id: string) => {
    try {
      await pauseTask.mutateAsync(id);
      toast.success(t('messages.paused'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleResume = async (id: string) => {
    try {
      await resumeTask.mutateAsync(id);
      toast.success(t('messages.resumed'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleRunNow = async (id: string) => {
    try {
      await runTaskNow.mutateAsync(id);
      toast.success(t('messages.runStarted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">{t('title')}</h1>
            <p className="text-muted-foreground mt-1">{t('description')}</p>
          </div>
          <Link href="/scheduled-tasks/new">
            <Button size="lg">
              <Plus className="mr-2 h-4 w-4" />
              {t('create')}
            </Button>
          </Link>
        </div>

        {/* Filter */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Select
            value={statusFilter || 'all'}
            onValueChange={(v) => setStatusFilter(v === 'all' ? undefined : v)}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder={t('fields.status')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{tc('filters.all')}</SelectItem>
              {STATUS_OPTIONS.map((status) => (
                <SelectItem key={status} value={status}>
                  {t(`statuses.${status}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Error State */}
        {error && (
          <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} className="mb-6" />
        )}

        {/* Loading State */}
        {isLoading && <LoadingSkeleton variant="card-grid" count={3} />}

        {/* Empty State */}
        {!isLoading && taskList.length === 0 && (
          <EmptyState
            icon={Clock}
            title={t('noTasks')}
            description={t('noTasksDescription')}
            action={
              <Link href="/scheduled-tasks/new">
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('create')}
                </Button>
              </Link>
            }
          />
        )}

        {/* Tasks Grid */}
        {!isLoading && taskList.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {taskList.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onDelete={() => handleDelete(task.id)}
                onPause={() => handlePause(task.id)}
                onResume={() => handleResume(task.id)}
                onRunNow={() => handleRunNow(task.id)}
                t={t}
                tc={tc}
              />
            ))}
          </div>
        )}

        {/* Stats */}
        {taskList.length > 0 && (
          <div className="mt-8 text-sm text-muted-foreground">
            {tc('status.total')}: {taskList.length}
          </div>
        )}
      </main>
    </div>
  );
}

function TaskCard({
  task,
  onDelete,
  onPause,
  onResume,
  onRunNow,
  t,
  tc,
}: {
  task: ScheduledTask;
  onDelete: () => void;
  onPause: () => void;
  onResume: () => void;
  onRunNow: () => void;
  t: (key: string) => string;
  tc: (key: string) => string;
}) {
  return (
    <Card className="group hover:shadow-md transition-shadow h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <CardTitle className="text-lg truncate">
              <Link href={`/scheduled-tasks/${task.id}`} className="hover:underline">
                {task.name}
              </Link>
            </CardTitle>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <StatusBadge status={task.status} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col">
        <div className="space-y-1.5 text-sm text-muted-foreground flex-1">
          {task.agent_name && (
            <div>
              <span className="font-medium">{t('fields.agent')}:</span>{' '}
              <span>{task.agent_name}</span>
            </div>
          )}
          <div>
            <span className="font-medium">{t('fields.scheduleType')}:</span>{' '}
            <span>{t(`scheduleTypes.${task.schedule_type}`)}</span>
          </div>
          <div>
            <span className="font-medium">{t('fields.scheduleValue')}:</span>{' '}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">{task.schedule_value}</code>
          </div>
          {task.next_run && (
            <div>
              <span className="font-medium">{t('fields.nextRun')}:</span>{' '}
              <span className="text-xs">{formatDateTime(task.next_run)}</span>
            </div>
          )}
          <div>
            <span className="font-medium">{t('fields.runCount')}:</span>{' '}
            <span>{task.run_count}{task.max_runs != null ? ` / ${task.max_runs}` : ''}</span>
          </div>
          <div className="text-xs text-muted-foreground/70">
            {formatDateTime(task.created_at)}
          </div>
        </div>
        <div className="flex items-center gap-2 mt-4 pt-4 border-t">
          <Link href={`/scheduled-tasks/${task.id}`} className="flex-1">
            <Button variant="outline" size="sm" className="w-full">
              {tc('actions.details')}
            </Button>
          </Link>
          {task.status === 'active' ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onPause}
              title={t('actions.pause')}
            >
              <Pause className="h-4 w-4 text-yellow-500" />
            </Button>
          ) : task.status === 'paused' ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onResume}
              title={t('actions.resume')}
            >
              <Play className="h-4 w-4 text-green-500" />
            </Button>
          ) : null}
          {task.status !== 'completed' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onRunNow}
              title={t('actions.runNow')}
            >
              <Zap className="h-4 w-4 text-blue-500" />
            </Button>
          )}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                aria-label={tc('actions.delete')}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{tc('actions.delete')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t('messages.confirmDelete')}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={(e) => {
                    e.preventDefault();
                    onDelete();
                  }}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {tc('actions.delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  );
}

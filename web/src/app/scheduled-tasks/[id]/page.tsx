'use client';

import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Trash2,
  Pause,
  Play,
  Zap,
  ExternalLink,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { ErrorBanner } from '@/components/ui/error-banner';
import { EmptyState } from '@/components/ui/empty-state';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { toast } from 'sonner';
import {
  useScheduledTask,
  useDeleteScheduledTask,
  usePauseTask,
  useResumeTask,
  useRunTaskNow,
  useTaskRuns,
} from '@/hooks/use-scheduled-tasks';
import { useTranslation } from '@/i18n/client';
import { formatDateTime, formatDuration } from '@/lib/formatters';

function StatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, 'success' | 'warning' | 'secondary'> = {
    active: 'success',
    paused: 'warning',
    completed: 'secondary',
  };
  return <Badge variant={variantMap[status] || 'secondary'}>{status}</Badge>;
}

function RunStatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, 'success' | 'info' | 'error'> = {
    completed: 'success',
    running: 'info',
    failed: 'error',
  };
  return <Badge variant={variantMap[status] || 'secondary'}>{status}</Badge>;
}

export default function ScheduledTaskDetailPage() {
  const router = useRouter();
  const params = useParams();
  const taskId = params.id as string;

  const { t } = useTranslation('scheduled-tasks');
  const { t: tc } = useTranslation('common');

  const { data: task, isLoading, error } = useScheduledTask(taskId);
  const deleteTask = useDeleteScheduledTask();
  const pauseTask = usePauseTask();
  const resumeTask = useResumeTask();
  const runTaskNow = useRunTaskNow();
  const { data: runs, isLoading: runsLoading } = useTaskRuns(taskId);

  const runList = runs || [];

  const handlePause = async () => {
    if (!task) return;
    try {
      await pauseTask.mutateAsync(task.id);
      toast.success(t('messages.paused'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleResume = async () => {
    if (!task) return;
    try {
      await resumeTask.mutateAsync(task.id);
      toast.success(t('messages.resumed'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleRunNow = async () => {
    if (!task) return;
    try {
      await runTaskNow.mutateAsync(task.id);
      toast.success(t('messages.runStarted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleDelete = async () => {
    if (!task) return;
    try {
      await deleteTask.mutateAsync(task.id);
      toast.success(t('messages.deleted'));
      router.push('/scheduled-tasks');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container px-4 py-8">
        <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="container px-4 py-8">
        <ErrorBanner title={tc('errors.generic')} message="Task not found" />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8 max-w-4xl">
        {/* Back Link */}
        <Link
          href="/scheduled-tasks"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('title')}
        </Link>

        {/* Task Details Card */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="text-2xl">{task.name}</CardTitle>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('detail.title')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {task.status === 'active' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePause}
                    disabled={pauseTask.isPending}
                  >
                    {pauseTask.isPending ? (
                      <Spinner size="sm" className="mr-2" />
                    ) : (
                      <Pause className="mr-2 h-4 w-4 text-yellow-500" />
                    )}
                    {t('actions.pause')}
                  </Button>
                ) : task.status === 'paused' ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResume}
                    disabled={resumeTask.isPending}
                  >
                    {resumeTask.isPending ? (
                      <Spinner size="sm" className="mr-2" />
                    ) : (
                      <Play className="mr-2 h-4 w-4 text-green-500" />
                    )}
                    {t('actions.resume')}
                  </Button>
                ) : null}
                {task.status !== 'completed' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRunNow}
                    disabled={runTaskNow.isPending}
                  >
                    {runTaskNow.isPending ? (
                      <Spinner size="sm" className="mr-2" />
                    ) : (
                      <Zap className="mr-2 h-4 w-4 text-blue-500" />
                    )}
                    {t('actions.runNow')}
                  </Button>
                )}
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" size="sm">
                      <Trash2 className="mr-2 h-4 w-4" />
                      {tc('actions.delete')}
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
                          handleDelete();
                        }}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        {tc('actions.delete')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.status')}</span>
                <div className="mt-1">
                  <StatusBadge status={task.status} />
                </div>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.agent')}</span>
                <p className="mt-1 text-sm">{task.agent_name || task.agent_id}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.scheduleType')}</span>
                <p className="mt-1 text-sm">{t(`scheduleTypes.${task.schedule_type}`)}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.scheduleValue')}</span>
                <p className="mt-1">
                  <code className="text-sm bg-muted px-2 py-1 rounded">{task.schedule_value}</code>
                </p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.contextMode')}</span>
                <p className="mt-1 text-sm">{t(`contextModes.${task.context_mode}`)}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.maxRuns')}</span>
                <p className="mt-1 text-sm">{task.max_runs != null ? task.max_runs : '-'}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.runCount')}</span>
                <p className="mt-1 text-sm">{task.run_count}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.nextRun')}</span>
                <p className="mt-1 text-sm">{task.next_run ? formatDateTime(task.next_run) : '-'}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{t('fields.lastRun')}</span>
                <p className="mt-1 text-sm">{task.last_run ? formatDateTime(task.last_run) : '-'}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{tc('fields.createdAt')}</span>
                <p className="mt-1 text-sm">{formatDateTime(task.created_at)}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-muted-foreground">{tc('fields.updatedAt')}</span>
                <p className="mt-1 text-sm">{formatDateTime(task.updated_at)}</p>
              </div>
              <div className="sm:col-span-2">
                <span className="text-sm font-medium text-muted-foreground">{t('fields.prompt')}</span>
                <p className="mt-1 text-sm whitespace-pre-wrap bg-muted rounded-md px-3 py-2">
                  {task.prompt}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Run History */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">{t('runs.title')}</CardTitle>
              {runList.length > 0 && (
                <span className="text-sm text-muted-foreground">
                  {runList.length} {tc('status.total').toLowerCase()}
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {runsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Spinner size="md" />
              </div>
            ) : runList.length === 0 ? (
              <EmptyState
                icon={Clock}
                title={t('runs.noRuns')}
                className="py-8"
              />
            ) : (
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">{t('fields.lastRun')}</TableHead>
                      <TableHead className="w-[100px]">{t('fields.status')}</TableHead>
                      <TableHead className="w-[100px]">Duration</TableHead>
                      <TableHead>Result</TableHead>
                      <TableHead className="w-[80px]">Trace</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runList.map((run) => (
                      <TableRow key={run.id}>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDateTime(run.started_at)}
                        </TableCell>
                        <TableCell>
                          <RunStatusBadge status={run.status} />
                        </TableCell>
                        <TableCell className="text-sm">
                          {formatDuration(run.duration_ms)}
                        </TableCell>
                        <TableCell className="text-sm max-w-md truncate">
                          {run.status === 'failed' && run.error ? (
                            <span className="text-destructive">{run.error}</span>
                          ) : (
                            run.result_summary || '-'
                          )}
                        </TableCell>
                        <TableCell>
                          {run.trace_id ? (
                            <Link
                              href={`/traces/${run.trace_id}`}
                              className="text-blue-500 hover:text-blue-600"
                              title="View trace"
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Link>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

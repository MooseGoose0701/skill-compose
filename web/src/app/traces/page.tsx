'use client';

import { useState } from 'react';
import Link from 'next/link';
import { History, CheckCircle, XCircle, Clock, Cpu, Loader2, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTraces } from '@/hooks/use-traces';
import { useTranslation } from '@/i18n/client';
import { formatDuration, formatDateTime } from '@/lib/formatters';
import { tracesApi } from '@/lib/api';

const PAGE_SIZE = 20;

export default function TracesPage() {
  const { t } = useTranslation('traces');
  const { t: tc } = useTranslation('common');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(0);

  const { data, isLoading, error } = useTraces({
    success: statusFilter === 'all' ? undefined : statusFilter === 'success',
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;
  const [isExporting, setIsExporting] = useState(false);

  // Reset to first page when filter changes
  const handleFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(0);
  };

  // Export all traces (with current filter)
  const handleExport = async () => {
    setIsExporting(true);
    try {
      const blob = await tracesApi.exportMany({
        success: statusFilter === 'all' ? undefined : statusFilter === 'success',
        limit: 1000,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `traces_export_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('export.error'));
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Main Content */}
      <main className="flex-1 container px-4 py-8 pb-24">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <History className="h-8 w-8" />
              {t('title')}
            </h1>
            <p className="text-muted-foreground mt-1">
              {t('description')}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleExport}
              disabled={isExporting || !data?.traces.length}
            >
              {isExporting ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-1" />
              )}
              {t('exportAll')}
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Select value={statusFilter} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={t('filterPlaceholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('all')}</SelectItem>
              <SelectItem value="success">{t('success')}</SelectItem>
              <SelectItem value="failed">{t('failed')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Error State */}
        {error && (
          <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} className="mb-6" />
        )}

        {/* Loading State */}
        {isLoading && (
          <LoadingSkeleton variant="list" count={3} />
        )}

        {/* Traces List */}
        {data && (
          <div className="space-y-4">
            {data.traces.length === 0 ? (
              <EmptyState
                icon={History}
                title={t('list.empty')}
                description={t('list.emptyDescription')}
              />
            ) : (
              data.traces.map((trace) => (
                <Link key={trace.id} href={`/traces/${trace.id}`} style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 100px' }}>
                  <Card className="p-4 hover:bg-muted/50 transition-colors cursor-pointer">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          {trace.status === 'running' ? (
                            <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
                          ) : trace.status === 'cancelled' ? (
                            <XCircle className="h-4 w-4 text-yellow-500" />
                          ) : trace.success ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-500" />
                          )}
                          <span className="font-medium truncate">
                            {trace.request}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDateTime(trace.created_at)}
                          </span>
                          <span className="flex items-center gap-1">
                            <Cpu className="h-3 w-3" />
                            {t('turns', { count: trace.total_turns })}
                          </span>
                          <span>
                            {t('tokens', { count: trace.total_input_tokens + trace.total_output_tokens })}
                          </span>
                          <span>{formatDuration(trace.duration_ms)}</span>
                        </div>
                        {trace.skills_used && trace.skills_used.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {trace.skills_used.map((skill) => (
                              <Badge key={skill} variant="outline" className="text-xs">
                                {skill}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                      <Badge variant={
                        trace.status === 'running' ? 'secondary' :
                        trace.status === 'cancelled' ? 'warning' :
                        trace.success ? 'default' : 'destructive'
                      }>
                        {trace.status === 'running' ? t('status.running') :
                         trace.status === 'cancelled' ? t('status.cancelled') :
                         trace.success ? t('status.completed') : t('status.failed')}
                      </Badge>
                    </div>
                  </Card>
                </Link>
              ))
            )}
          </div>
        )}

        {/* Pagination */}
        {data && data.total > PAGE_SIZE && (
          <div className="mt-6 flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {t('showing', { from: page * PAGE_SIZE + 1, to: Math.min((page + 1) * PAGE_SIZE, data.total), total: data.total })}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p - 1)}
                disabled={page === 0}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                {tc('actions.previous')}
              </Button>
              <span className="text-sm text-muted-foreground px-2">
                {t('page', { current: page + 1, total: totalPages })}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page + 1 >= totalPages}
              >
                {tc('actions.next')}
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* Stats (when no pagination needed) */}
        {data && data.total > 0 && data.total <= PAGE_SIZE && (
          <div className="mt-8 text-sm text-muted-foreground">
            {t('showingAll', { count: data.traces.length, total: data.total })}
          </div>
        )}
      </main>
    </div>
  );
}

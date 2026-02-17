'use client';

import { Container, Cpu, HardDrive, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import { useExecutors } from '@/hooks/use-executors';
import { useTranslation } from '@/i18n/client';
import type { Executor } from '@/lib/api';

export default function ExecutorsPage() {
  const { t } = useTranslation('executors');
  const { data, isLoading, error, dataUpdatedAt, refetch, isFetching } = useExecutors();

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">{t('title')}</h1>
            <p className="text-muted-foreground mt-1">
              {t('description')}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {dataUpdatedAt > 0 && (
              <span className="text-xs text-muted-foreground">
                {t('lastUpdated', { time: new Date(dataUpdatedAt).toLocaleTimeString() })}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={`h-4 w-4 mr-1.5 ${isFetching ? 'animate-spin' : ''}`} />
              {t('refresh')}
            </Button>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <ErrorBanner
            title={t('failedToLoad')}
            message={(error as Error).message}
            className="mb-6"
          />
        )}

        {/* Loading State */}
        {isLoading && <LoadingSkeleton variant="card-grid" count={3} />}

        {/* Empty State */}
        {!isLoading && data?.executors.length === 0 && (
          <EmptyState
            icon={Container}
            title={t('noExecutors')}
            description={t('noExecutorsDescription')}
          />
        )}

        {/* Executors Grid */}
        {!isLoading && data && data.executors.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {data.executors.map((executor) => (
              <ExecutorCard key={executor.id} executor={executor} t={t} />
            ))}
          </div>
        )}

        {/* Stats */}
        {data && (
          <div className="mt-8 text-sm text-muted-foreground">
            {t('total', { count: data.total })}
          </div>
        )}
      </main>
    </div>
  );
}

function ExecutorCard({
  executor,
  t,
}: {
  executor: Executor;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const statusConfig = {
    online: { color: 'bg-green-500', labelKey: 'status.online', variant: 'success' as const },
    offline: { color: 'bg-gray-400', labelKey: 'status.offline', variant: 'secondary' as const },
  };

  const config = statusConfig[executor.status] || statusConfig.offline;

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${config.color}`} aria-hidden="true" />
            <CardTitle className="text-lg">{executor.name}</CardTitle>
          </div>
          <Badge variant={config.variant}>{t(config.labelKey)}</Badge>
        </div>
        {executor.description && (
          <CardDescription className="line-clamp-2">
            {executor.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex-1 flex flex-col">
        <div className="space-y-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Container className="h-4 w-4" />
            <code className="text-xs truncate flex-1">{executor.image}</code>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <HardDrive className="h-4 w-4" />
              <span>{executor.memory_limit || '2G'}</span>
            </div>
            {executor.gpu_required && (
              <Badge variant="secondary" className="text-xs">
                <Cpu className="h-3 w-3 mr-1" />
                GPU
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

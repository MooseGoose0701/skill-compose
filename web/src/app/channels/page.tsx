'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Radio, Plus, Trash2, ToggleLeft, ToggleRight, Wifi, WifiOff, RefreshCw } from 'lucide-react';
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
  useChannelBindings,
  useDeleteChannelBinding,
  useToggleChannelBinding,
  useAdapterStatus,
} from '@/hooks/use-channels';
import { useTranslation } from '@/i18n/client';
import { formatDateTime } from '@/lib/formatters';
import type { ChannelBinding } from '@/lib/api';
import { channelsApi } from '@/lib/api';

const CHANNEL_TYPES = ['feishu', 'telegram', 'webhook'] as const;

function ChannelTypeBadge({ type }: { type: string }) {
  const variantMap: Record<string, 'default' | 'info' | 'purple'> = {
    feishu: 'info',
    telegram: 'purple',
    webhook: 'default',
  };
  return <Badge variant={variantMap[type] || 'default'}>{type}</Badge>;
}

export default function ChannelsPage() {
  const { t } = useTranslation('channels');
  const { t: tc } = useTranslation('common');

  const [channelTypeFilter, setChannelTypeFilter] = useState<string | undefined>(undefined);

  const { data, isLoading, error } = useChannelBindings(
    channelTypeFilter ? { channel_type: channelTypeFilter } : undefined
  );
  const { data: adapterStatus, isLoading: isAdapterLoading } = useAdapterStatus();
  const deleteBinding = useDeleteChannelBinding();
  const toggleBinding = useToggleChannelBinding();

  const bindings = useMemo(() => data?.bindings || [], [data?.bindings]);

  const handleDelete = async (id: string) => {
    try {
      await deleteBinding.mutateAsync(id);
      toast.success(t('messages.deleted'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleToggle = async (id: string) => {
    try {
      await toggleBinding.mutateAsync(id);
      toast.success(t('messages.toggled'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  const handleRestartAdapter = async (adapterType: string) => {
    try {
      const result = await channelsApi.restartAdapter(adapterType);
      toast.success(result.message);
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
          <Link href="/channels/new">
            <Button size="lg">
              <Plus className="mr-2 h-4 w-4" />
              {t('create')}
            </Button>
          </Link>
        </div>

        {/* Adapter Status Section */}
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('adapters.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            {isAdapterLoading ? (
              <Spinner size="sm" />
            ) : adapterStatus && Object.keys(adapterStatus).length > 0 ? (
              <div className="flex flex-wrap gap-3">
                {Object.entries(adapterStatus).map(([key, connected]) => {
                  // Parse adapter key: "feishu:cli_xxx" → "Feishu (cli_xxx...)"
                  let displayName = key;
                  if (key.startsWith('feishu:')) {
                    const appId = key.slice(7);
                    const truncated = appId.length > 12 ? appId.slice(0, 12) + '...' : appId;
                    displayName = `Feishu (${truncated})`;
                  } else {
                    displayName = key.charAt(0).toUpperCase() + key.slice(1);
                  }

                  return (
                    <div key={key} className="flex items-center gap-2 rounded-lg border px-3 py-2">
                      {connected ? (
                        <Wifi className="h-4 w-4 text-green-500" />
                      ) : (
                        <WifiOff className="h-4 w-4 text-red-500" />
                      )}
                      <span className="text-sm font-medium">{displayName}</span>
                      <Badge variant={connected ? 'success' : 'error'} className="text-xs">
                        {connected ? t('adapters.connected') : t('adapters.disconnected')}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => handleRestartAdapter(key)}
                        title={t('adapters.restart')}
                      >
                        <RefreshCw className="h-3 w-3" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{t('adapters.noAdapters')}</p>
            )}
          </CardContent>
        </Card>

        {/* Filter */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Select
            value={channelTypeFilter || 'all'}
            onValueChange={(v) => setChannelTypeFilter(v === 'all' ? undefined : v)}
          >
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder={t('fields.channelType')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{tc('filters.all')}</SelectItem>
              {CHANNEL_TYPES.map((type) => (
                <SelectItem key={type} value={type}>
                  {t(`channelTypes.${type}`)}
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
        {!isLoading && bindings.length === 0 && (
          <EmptyState
            icon={Radio}
            title={t('noBindings')}
            description={t('noBindingsDescription')}
            action={
              <Link href="/channels/new">
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  {t('create')}
                </Button>
              </Link>
            }
          />
        )}

        {/* Bindings Grid */}
        {!isLoading && bindings.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {bindings.map((binding) => (
              <BindingCard
                key={binding.id}
                binding={binding}
                onDelete={() => handleDelete(binding.id)}
                onToggle={() => handleToggle(binding.id)}
                t={t}
                tc={tc}
              />
            ))}
          </div>
        )}

        {/* Stats */}
        {data && (
          <div className="mt-8 text-sm text-muted-foreground">
            {tc('status.total')}: {data.total}
          </div>
        )}
      </main>
    </div>
  );
}

function BindingCard({
  binding,
  onDelete,
  onToggle,
  t,
  tc,
}: {
  binding: ChannelBinding;
  onDelete: () => void;
  onToggle: () => void;
  t: (key: string) => string;
  tc: (key: string) => string;
}) {
  return (
    <Card className="group hover:shadow-md transition-shadow h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <CardTitle className="text-lg truncate">
              <Link href={`/channels/${binding.id}`} className="hover:underline">
                {binding.name}
              </Link>
            </CardTitle>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <ChannelTypeBadge type={binding.channel_type} />
            <Badge variant={binding.enabled ? 'success' : 'secondary'} className="text-xs">
              {binding.enabled ? t('actions.enable') : t('actions.disable')}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col">
        <div className="space-y-1.5 text-sm text-muted-foreground flex-1">
          <div>
            <span className="font-medium">{t('fields.externalId')}:</span>{' '}
            <span className="font-mono text-xs">{binding.external_id}</span>
          </div>
          {binding.trigger_pattern && (
            <div>
              <span className="font-medium">{t('fields.triggerPattern')}:</span>{' '}
              <code className="text-xs bg-muted px-1 py-0.5 rounded">{binding.trigger_pattern}</code>
            </div>
          )}
          <div className="text-xs text-muted-foreground/70">
            {formatDateTime(binding.created_at)}
          </div>
        </div>
        <div className="flex items-center gap-2 mt-4 pt-4 border-t">
          <Link href={`/channels/${binding.id}`} className="flex-1">
            <Button variant="outline" size="sm" className="w-full">
              {tc('actions.details')}
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            title={t('actions.toggle')}
          >
            {binding.enabled ? (
              <ToggleRight className="h-4 w-4 text-green-500" />
            ) : (
              <ToggleLeft className="h-4 w-4 text-muted-foreground" />
            )}
          </Button>
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

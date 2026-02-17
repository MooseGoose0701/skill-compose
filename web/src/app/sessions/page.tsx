'use client';

import { useState } from 'react';
import Link from 'next/link';
import { MessageSquare, Clock, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
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
import { usePublishedSessions, useDeletePublishedSession } from '@/hooks/use-published-sessions';
import { useQuery } from '@tanstack/react-query';
import { agentPresetsApi } from '@/lib/api';
import { useTranslation } from '@/i18n/client';
import { formatDateTime } from '@/lib/formatters';

const PAGE_SIZE = 20;

export default function SessionsPage() {
  const { t } = useTranslation('sessions');
  const { t: tc } = useTranslation('common');
  const [agentFilter, setAgentFilter] = useState<string>('all');
  const [page, setPage] = useState(0);

  const { data, isLoading, error } = usePublishedSessions({
    agentId: agentFilter === 'all' ? undefined : agentFilter,
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
  });

  // Fetch published agents for filter dropdown
  const { data: agentsData } = useQuery({
    queryKey: ['agents-published'],
    queryFn: async () => {
      const result = await agentPresetsApi.list();
      return result.presets.filter((p) => p.is_published);
    },
  });

  const CHAT_SENTINEL = '__chat__';

  const deleteMutation = useDeletePublishedSession();
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  const handleFilterChange = (value: string) => {
    setAgentFilter(value);
    setPage(0);
  };

  const handleDelete = async (sessionId: string) => {
    try {
      await deleteMutation.mutateAsync(sessionId);
      toast.success(t('delete.success'));
    } catch {
      toast.error(t('delete.error'));
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8 pb-24">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <MessageSquare className="h-8 w-8" />
              {t('title')}
            </h1>
            <p className="text-muted-foreground mt-1">
              {t('description')}
            </p>
          </div>
        </div>

        {/* Filter */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Select value={agentFilter} onValueChange={handleFilterChange}>
            <SelectTrigger className="w-[240px]">
              <SelectValue placeholder={t('filters.allAgents')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('filters.allAgents')}</SelectItem>
              <SelectItem value={CHAT_SENTINEL}>{t('filters.chatSessions')}</SelectItem>
              {agentsData?.map((agent) => (
                <SelectItem key={agent.id} value={agent.id}>
                  {agent.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Error */}
        {error && (
          <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} className="mb-6" />
        )}

        {/* Loading */}
        {isLoading && <LoadingSkeleton variant="list" count={3} />}

        {/* Sessions List */}
        {data && (
          <div className="space-y-4">
            {data.sessions.length === 0 ? (
              <EmptyState
                icon={MessageSquare}
                title={t('empty')}
                description={t('emptyDescription')}
              />
            ) : (
              data.sessions.map((session) => (
                <div key={session.id} className="group relative" style={{ contentVisibility: 'auto', containIntrinsicSize: 'auto 80px' }}>
                  <Link href={`/sessions/${session.id}`}>
                    <Card className="p-4 hover:bg-muted/50 transition-colors cursor-pointer">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                            <span className="font-medium truncate">
                              {session.first_user_message || t('card.noMessage')}
                            </span>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                            {session.agent_id === CHAT_SENTINEL ? (
                              <Badge variant="secondary">{t('filters.chatBadge')}</Badge>
                            ) : session.agent_name ? (
                              <Badge variant="outline">{session.agent_name}</Badge>
                            ) : null}
                            <span>{t('card.messageCount', { count: session.message_count })}</span>
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatDateTime(session.created_at)}
                            </span>
                            <span className="text-xs">
                              {t('card.lastActive')}: {formatDateTime(session.updated_at)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </Card>
                  </Link>
                  {/* Delete button overlay */}
                  <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => e.preventDefault()}
                          aria-label={t('delete.title')}
                        >
                          <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>{t('delete.title')}</AlertDialogTitle>
                          <AlertDialogDescription>{t('delete.confirm')}</AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleDelete(session.id)}>
                            {tc('actions.delete')}
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Pagination */}
        {data && data.total > PAGE_SIZE && (
          <div className="mt-6 flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {t('pagination.showing', { from: page * PAGE_SIZE + 1, to: Math.min((page + 1) * PAGE_SIZE, data.total), total: data.total })}
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
                {t('pagination.page', { current: page + 1, total: totalPages })}
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

        {/* Stats (no pagination needed) */}
        {data && data.total > 0 && data.total <= PAGE_SIZE && (
          <div className="mt-8 text-sm text-muted-foreground">
            {t('pagination.showingAll', { count: data.sessions.length, total: data.total })}
          </div>
        )}
      </main>
    </div>
  );
}

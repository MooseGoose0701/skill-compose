'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { MessageSquare, ArrowLeft, Trash2, Clock } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { ErrorBanner } from '@/components/ui/error-banner';
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
import { usePublishedSessionDetail, useDeletePublishedSession } from '@/hooks/use-published-sessions';
import { useQuery } from '@tanstack/react-query';
import { agentPresetsApi } from '@/lib/api';
import { ChatMessageItem } from '@/components/chat/chat-message';
import type { ChatMessage } from '@/stores/chat-store';
import { sessionMessagesToChatMessages } from '@/lib/session-utils';
import { useTranslation } from '@/i18n/client';
import { formatDateTime } from '@/lib/formatters';

const CHAT_SENTINEL = '__chat__';

// ---------- main page ----------
export default function SessionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;
  const { t } = useTranslation('sessions');
  const { t: tc } = useTranslation('common');

  const { data: session, isLoading, error } = usePublishedSessionDetail(sessionId);
  const deleteMutation = useDeletePublishedSession();

  const isChat = session?.agent_id === CHAT_SENTINEL;

  const { data: agent } = useQuery({
    queryKey: ['agent', session?.agent_id],
    queryFn: () => agentPresetsApi.get(session!.agent_id),
    enabled: !!session?.agent_id && !isChat,
  });

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(sessionId);
      toast.success(t('delete.success'));
      router.push('/sessions');
    } catch {
      toast.error(t('delete.error'));
    }
  };

  const chatMessages = React.useMemo(
    () => sessionMessagesToChatMessages(
      (session?.messages || []) as Array<{ role: string; content: string | Array<Record<string, unknown>> }>
    ),
    [session?.messages]
  );

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8 pb-24 max-w-4xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-6 text-sm text-muted-foreground">
          <Link href="/sessions" className="flex items-center gap-1 hover:text-foreground transition-colors">
            <ArrowLeft className="h-4 w-4" />
            {t('title')}
          </Link>
          <span>/</span>
          <span className="truncate max-w-[200px]">{sessionId}</span>
        </div>

        {error && (
          <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} className="mb-6" />
        )}

        {isLoading && <LoadingSkeleton variant="detail" />}

        {session && (
          <>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
              <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                  <MessageSquare className="h-6 w-6" />
                  {t('detail.title')}
                </h1>
                <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-muted-foreground">
                  {isChat ? (
                    <Badge variant="secondary">{t('detail.chatBadge')}</Badge>
                  ) : agent ? (
                    <Badge variant="outline">{agent.name}</Badge>
                  ) : null}
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDateTime(session.created_at)}
                  </span>
                  <span>{t('card.messageCount', { count: (session.messages || []).length })}</span>
                </div>
              </div>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Trash2 className="h-4 w-4 mr-1" />
                    {tc('actions.delete')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('delete.title')}</AlertDialogTitle>
                    <AlertDialogDescription>{t('delete.confirm')}</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDelete}>
                      {tc('actions.delete')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>

            {/* Messages — reuse ChatMessageItem from chat panel */}
            <div className="space-y-3">
              {chatMessages.length === 0 ? (
                <p className="text-center text-muted-foreground py-12">{t('detail.noMessages')}</p>
              ) : (
                chatMessages.map((msg) => (
                  <ChatMessageItem
                    key={msg.id}
                    message={msg}
                    hideTraceLink
                  />
                ))
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

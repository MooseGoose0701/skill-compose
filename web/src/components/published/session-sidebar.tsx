'use client';

import React, { useState, useMemo } from 'react';
import { MessageSquarePlus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
import { usePublishedSessions, useDeletePublishedSession } from '@/hooks/use-published-sessions';
import { useTranslation } from '@/i18n/client';
import { formatRelativeTime } from '@/lib/formatters';
import { toast } from 'sonner';
import type { SessionListItem } from '@/lib/api';

interface SessionSidebarProps {
  agentId: string;
  activeSessionId: string;
  onSessionSelect: (sessionId: string) => void;
  onNewChat: () => void;
  isRunning: boolean;
}

interface SessionGroup {
  label: string;
  sessions: SessionListItem[];
}

function groupSessionsByDate(sessions: SessionListItem[], labels: {
  today: string;
  yesterday: string;
  previous7Days: string;
  older: string;
}): SessionGroup[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 6 * 86400000;

  const groups: Record<string, SessionListItem[]> = {
    today: [],
    yesterday: [],
    previous7Days: [],
    older: [],
  };

  for (const session of sessions) {
    const ts = new Date(session.updated_at).getTime();
    if (ts >= todayStart) {
      groups.today.push(session);
    } else if (ts >= yesterdayStart) {
      groups.yesterday.push(session);
    } else if (ts >= weekStart) {
      groups.previous7Days.push(session);
    } else {
      groups.older.push(session);
    }
  }

  const result: SessionGroup[] = [];
  if (groups.today.length > 0) result.push({ label: labels.today, sessions: groups.today });
  if (groups.yesterday.length > 0) result.push({ label: labels.yesterday, sessions: groups.yesterday });
  if (groups.previous7Days.length > 0) result.push({ label: labels.previous7Days, sessions: groups.previous7Days });
  if (groups.older.length > 0) result.push({ label: labels.older, sessions: groups.older });
  return result;
}

export function SessionSidebar({
  agentId,
  activeSessionId,
  onSessionSelect,
  onNewChat,
  isRunning,
}: SessionSidebarProps) {
  const { t } = useTranslation('chat');
  const { data, isLoading } = usePublishedSessions({ agentId, limit: 50 });
  const deleteMutation = useDeletePublishedSession();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const sessions = data?.sessions ?? [];

  const groups = useMemo(() => {
    return groupSessionsByDate(sessions, {
      today: t('published.sidebar.today'),
      yesterday: t('published.sidebar.yesterday'),
      previous7Days: t('published.sidebar.previous7Days'),
      older: t('published.sidebar.older'),
    });
  }, [sessions, t]);

  const handleDelete = async (sessionId: string) => {
    setDeletingId(sessionId);
    try {
      await deleteMutation.mutateAsync(sessionId);
      toast.success(t('published.sidebar.deleted'));
      if (sessionId === activeSessionId) {
        onNewChat();
      }
    } catch {
      toast.error(t('published.sidebar.deleteError'));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* New Chat button */}
      <div className="p-3 border-b">
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={onNewChat}
          disabled={isRunning}
        >
          <MessageSquarePlus className="h-4 w-4" />
          {t('newChat')}
        </Button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Spinner size="sm" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="px-3 py-8 text-center text-sm text-muted-foreground">
            {t('published.sidebar.noSessions')}
          </div>
        ) : (
          <div className="py-2">
            {groups.map((group) => (
              <div key={group.label}>
                <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {group.label}
                </div>
                {group.sessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    isActive={session.id === activeSessionId}
                    isDeleting={session.id === deletingId}
                    isRunning={isRunning}
                    onSelect={() => onSessionSelect(session.id)}
                    onDelete={() => handleDelete(session.id)}
                    t={t}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SessionItem({
  session,
  isActive,
  isDeleting,
  isRunning,
  onSelect,
  onDelete,
  t,
}: {
  session: SessionListItem;
  isActive: boolean;
  isDeleting: boolean;
  isRunning: boolean;
  onSelect: () => void;
  onDelete: () => void;
  t: (key: string, options?: Record<string, unknown>) => string;
}) {
  const preview = session.first_user_message || t('published.sidebar.emptyMessage');
  const msgCount = session.message_count;
  const timeAgo = formatRelativeTime(session.updated_at);

  return (
    <div
      className={`group relative mx-1.5 mb-0.5 rounded-lg cursor-pointer transition-colors ${
        isActive
          ? 'bg-accent text-accent-foreground'
          : 'hover:bg-muted/50'
      } ${isDeleting ? 'opacity-50 pointer-events-none' : ''}`}
      onClick={() => {
        if (!isRunning && !isActive) onSelect();
      }}
    >
      <div className="px-3 py-2.5 pr-9">
        <div className="text-sm font-medium truncate leading-snug">
          {preview}
        </div>
        <div className="flex items-center gap-1.5 mt-1 text-xs text-muted-foreground">
          <span>{t('published.sidebar.messagesCount', { count: msgCount })}</span>
          <span>·</span>
          <span>{timeAgo}</span>
        </div>
      </div>

      {/* Delete button - visible on hover */}
      <div className="absolute right-1.5 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button
              className="p-1.5 rounded-md hover:bg-destructive/10 hover:text-destructive transition-colors"
              onClick={(e) => e.stopPropagation()}
              title={t('published.sidebar.deleteConfirm')}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('published.sidebar.deleteConfirm')}</AlertDialogTitle>
              <AlertDialogDescription>{t('published.sidebar.deleteDescription')}</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('close', { ns: 'chat' })}</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                <Trash2 className="h-4 w-4 mr-1" />
                {t('clear', { ns: 'chat' })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}

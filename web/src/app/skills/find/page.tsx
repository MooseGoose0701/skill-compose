'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { ArrowLeft, PanelLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SessionSidebar } from '@/components/published/session-sidebar';
import { SkillFinderChat } from '@/components/skill/skill-finder-chat';
import { useTranslation } from '@/i18n/client';
import { agentPresetsApi, agentApi } from '@/lib/api';
import { generateUUID } from '@/lib/utils';
import { sessionMessagesToChatMessages } from '@/lib/session-utils';
import { useQueryClient } from '@tanstack/react-query';
import { publishedSessionKeys } from '@/hooks/use-published-sessions';
import { Spinner } from '@/components/ui/spinner';
import type { ChatMessage } from '@/stores/chat-store';

const SESSION_STORAGE_KEY = 'skill-finder-session';

function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return generateUUID();
  const existing = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const id = generateUUID();
  sessionStorage.setItem(SESSION_STORAGE_KEY, id);
  return id;
}

export default function FindSkillsPage() {
  const queryClient = useQueryClient();
  const { t } = useTranslation('skills');

  const [skillFinderId, setSkillFinderId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [restoringSession, setRestoringSession] = useState(false);

  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Fetch skill-finder preset
  useEffect(() => {
    const fetchSkillFinder = async () => {
      try {
        setLoadError(null);
        const preset = await agentPresetsApi.getByName('skill-finder');
        setSkillFinderId(preset.id);
      } catch (error) {
        console.error('Failed to fetch skill-finder:', error);
        setLoadError(error instanceof Error ? error.message : 'Failed to load skill-finder preset');
      }
    };
    fetchSkillFinder();
  }, []);

  // Restore session on mount
  useEffect(() => {
    if (!skillFinderId) return;

    const restoreSession = async () => {
      setRestoringSession(true);
      try {
        const sessionData = await agentApi.getSession(sessionId);
        if (sessionData.messages.length > 0) {
          setMessages(sessionMessagesToChatMessages(sessionData.messages));
        }
      } catch {
        // Session not found — first visit
      } finally {
        setRestoringSession(false);
      }
    };
    restoreSession();
  }, [skillFinderId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh session list when chat completes
  const prevIsRunning = useRef(isRunning);
  useEffect(() => {
    if (prevIsRunning.current && !isRunning) {
      queryClient.invalidateQueries({ queryKey: publishedSessionKeys.lists() });
    }
    prevIsRunning.current = isRunning;
  }, [isRunning, queryClient]);

  const handleNewChat = useCallback(() => {
    const newId = generateUUID();
    sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
    setSessionId(newId);
    setMessages([]);
    setMobileSidebarOpen(false);
  }, []);

  const handleSessionSwitch = useCallback(async (newSessionId: string) => {
    if (newSessionId === sessionId || isRunning) return;

    sessionStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
    setSessionId(newSessionId);
    setMessages([]);
    setMobileSidebarOpen(false);

    try {
      const data = await agentApi.getSession(newSessionId);
      if (data.messages.length > 0) {
        setMessages(sessionMessagesToChatMessages(data.messages));
      }
    } catch {
      // First visit or not found
    }
  }, [sessionId, isRunning]);

  // Loading state
  if (!skillFinderId && !loadError) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-57px)]">
        <div className="text-center">
          <Spinner size="md" className="mx-auto mb-4" />
          <p className="text-muted-foreground">{t('find.loadingFinder')}</p>
          <p className="text-xs text-muted-foreground mt-2">{t('find.loadingFinderHint')}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (loadError) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-57px)]">
        <div className="text-center">
          <div className="h-8 w-8 mx-auto mb-4 text-destructive text-2xl">&#10005;</div>
          <p className="text-destructive font-medium">{t('find.loadError')}</p>
          <p className="text-xs text-muted-foreground mt-2">{loadError}</p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => window.location.reload()}>
            {t('find.retry')}
          </Button>
        </div>
      </div>
    );
  }

  // Restoring session
  if (restoringSession) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-57px)]">
        <Spinner size="md" />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-57px)]">
      {/* Desktop sidebar */}
      <div className="w-[260px] shrink-0 hidden md:flex flex-col border-r bg-muted/30">
        <SessionSidebar
          agentId={skillFinderId!}
          activeSessionId={sessionId}
          onSessionSelect={handleSessionSwitch}
          onNewChat={handleNewChat}
          isRunning={isRunning}
        />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-background border-r shadow-xl flex flex-col animate-in slide-in-from-left duration-200">
            <SessionSidebar
              agentId={skillFinderId!}
              activeSessionId={sessionId}
              onSessionSelect={handleSessionSwitch}
              onNewChat={handleNewChat}
              isRunning={isRunning}
            />
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <div className="border-b px-4 py-2 flex items-center gap-3 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden p-1.5"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <PanelLeft className="h-5 w-5" />
          </Button>
          <Link
            href="/skills"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            <span className="hidden sm:inline">{t('find.backToSkills')}</span>
          </Link>
        </div>

        {/* Chat content */}
        <SkillFinderChat
          skillFinderId={skillFinderId!}
          sessionId={sessionId}
          messages={messages}
          setMessages={setMessages}
          isRunning={isRunning}
          setIsRunning={setIsRunning}
        />
      </div>
    </div>
  );
}

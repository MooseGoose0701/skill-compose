'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, FileText, MessageSquare, PanelLeft } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useCreateAgentPreset } from '@/hooks/use-agents';
import { AgentBuilderChat } from '@/components/agents/agent-builder-chat';
import { AgentConfigForm, type AgentFormValues } from '@/components/agents/agent-config-form';
import { SessionSidebar } from '@/components/published/session-sidebar';
import { useTranslation } from '@/i18n/client';
import { agentPresetsApi, agentApi } from '@/lib/api';
import { generateUUID } from '@/lib/utils';
import { sessionMessagesToChatMessages } from '@/lib/session-utils';
import { useQueryClient } from '@tanstack/react-query';
import { publishedSessionKeys } from '@/hooks/use-published-sessions';
import { Spinner } from '@/components/ui/spinner';
import type { ChatMessage } from '@/stores/chat-store';

const SESSION_STORAGE_KEY = 'agent-builder-session';

function TabSwitcher({
  active,
  onTabChange,
  chatLabel,
  formLabel,
  className = '',
  size = 'sm',
}: {
  active: string;
  onTabChange: (tab: 'chat' | 'form') => void;
  chatLabel: string;
  formLabel: string;
  className?: string;
  size?: 'sm' | 'md';
}) {
  const py = size === 'sm' ? 'py-1.5' : 'py-2';
  const iconSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';
  return (
    <div className={`flex items-center rounded-lg bg-muted p-0.5 ${className}`}>
      <button
        onClick={() => onTabChange('chat')}
        className={`flex-1 flex items-center justify-center gap-1.5 px-3 ${py} text-sm rounded-md transition-colors ${
          active === 'chat'
            ? 'bg-background shadow-sm font-medium'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        <MessageSquare className={iconSize} />
        {chatLabel}
      </button>
      <button
        onClick={() => onTabChange('form')}
        className={`flex-1 flex items-center justify-center gap-1.5 px-3 ${py} text-sm rounded-md transition-colors ${
          active === 'form'
            ? 'bg-background shadow-sm font-medium'
            : 'text-muted-foreground hover:text-foreground'
        }`}
      >
        <FileText className={iconSize} />
        {formLabel}
      </button>
    </div>
  );
}

function getOrCreateSessionId(): string {
  if (typeof window === 'undefined') return generateUUID();
  const existing = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const id = generateUUID();
  sessionStorage.setItem(SESSION_STORAGE_KEY, id);
  return id;
}

export default function NewAgentPage() {
  const router = useRouter();
  const createPreset = useCreateAgentPreset();
  const queryClient = useQueryClient();
  const { t } = useTranslation('agents');

  // Active tab
  const [activeTab, setActiveTab] = useState<'chat' | 'form'>('chat');

  // Agent builder preset
  const [agentBuilderId, setAgentBuilderId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Session + chat state (lifted from AgentBuilderChat)
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [restoringSession, setRestoringSession] = useState(false);

  // Mobile sidebar
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Fetch agent-builder preset
  useEffect(() => {
    const fetchAgentBuilder = async () => {
      try {
        setLoadError(null);
        const preset = await agentPresetsApi.getByName('agent-builder');
        setAgentBuilderId(preset.id);
      } catch (error) {
        console.error('Failed to fetch agent-builder:', error);
        setLoadError(error instanceof Error ? error.message : 'Failed to load agent-builder preset');
      }
    };
    fetchAgentBuilder();
  }, []);

  // Restore session on mount (after agentBuilderId is loaded)
  useEffect(() => {
    if (!agentBuilderId) return;

    const restoreSession = async () => {
      setRestoringSession(true);
      try {
        const sessionData = await agentApi.getSession(sessionId);
        if (sessionData.messages.length > 0) {
          setMessages(sessionMessagesToChatMessages(sessionData.messages));
        }
      } catch {
        // Session not found — first visit, that's fine
      } finally {
        setRestoringSession(false);
      }
    };
    restoreSession();
  }, [agentBuilderId]); // Only on initial load, not on sessionId changes

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

  const handleSubmit = async (values: AgentFormValues) => {
    const preset = await createPreset.mutateAsync({
      name: values.name,
      description: values.description || undefined,
      system_prompt: values.system_prompt || undefined,
      skill_ids: values.skill_ids.length > 0 ? values.skill_ids : undefined,
      builtin_tools: values.builtin_tools.length > 0 ? values.builtin_tools : undefined,
      mcp_servers: values.mcp_servers.length > 0 ? values.mcp_servers : undefined,
      max_turns: values.max_turns,
      model_provider: values.model_provider || undefined,
      model_name: values.model_name || undefined,
      executor_id: values.executor_id || undefined,
    });
    router.push(`/agents/${preset.id}`);
  };

  // ── Chat tab layout ──
  if (activeTab === 'chat') {
    // Loading state
    if (!agentBuilderId && !loadError) {
      return (
        <div className="flex items-center justify-center h-[calc(100vh-57px)]">
          <div className="text-center">
            <Spinner size="md" className="mx-auto mb-4" />
            <p className="text-muted-foreground">{t('create.loadingBuilder')}</p>
            <p className="text-xs text-muted-foreground mt-2">{t('create.loadingBuilderHint')}</p>
          </div>
        </div>
      );
    }

    // Error state
    if (loadError) {
      return (
        <div className="flex items-center justify-center h-[calc(100vh-57px)]">
          <div className="text-center">
            <div className="h-8 w-8 mx-auto mb-4 text-destructive text-2xl">✕</div>
            <p className="text-destructive font-medium">{t('create.loadError')}</p>
            <p className="text-xs text-muted-foreground mt-2">{loadError}</p>
            <div className="flex items-center gap-2 justify-center mt-4">
              <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
                {t('create.retry')}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setActiveTab('form')}>
                {t('create.tabManual')}
              </Button>
            </div>
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
            agentId={agentBuilderId!}
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
                agentId={agentBuilderId!}
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
          {/* Tab switcher header */}
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
              href="/agents"
              className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="mr-1 h-4 w-4" />
              <span className="hidden sm:inline">{t('create.backToAgents')}</span>
            </Link>
            <div className="flex-1" />
            <TabSwitcher
              active={activeTab}
              onTabChange={setActiveTab}
              chatLabel={t('create.tabChat')}
              formLabel={t('create.tabManual')}
            />
          </div>

          {/* Chat content */}
          <AgentBuilderChat
            agentBuilderId={agentBuilderId!}
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

  // ── Form tab layout ──
  return (
    <div className="container mx-auto py-8 max-w-3xl">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/agents"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('create.backToAgents')}
        </Link>
        <h1 className="text-3xl font-bold">{t('create.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('create.subtitle')}</p>
      </div>

      {/* Tab switcher */}
      <TabSwitcher
        active={activeTab}
        onTabChange={setActiveTab}
        chatLabel={t('create.tabChat')}
        formLabel={t('create.tabManual')}
        className="mb-6"
        size="md"
      />

      {/* Form Mode */}
      <Card>
        <CardHeader>
          <CardTitle>{t('create.formTitle')}</CardTitle>
          <CardDescription>{t('create.formDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <AgentConfigForm
            mode="create"
            isProcessing={createPreset.isPending}
            onSubmit={handleSubmit}
          />
        </CardContent>
      </Card>
    </div>
  );
}

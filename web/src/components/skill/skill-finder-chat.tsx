'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Search, CheckCircle2, Settings2, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { agentApi, modelsApi, type StreamEvent, type UploadedFile } from '@/lib/api';
import { ChatMessageItem } from '@/components/chat/chat-message';
import { ModelSelect } from '@/components/chat/selects';
import type { ChatMessage } from '@/stores/chat-store';
import { useChatEngine } from '@/hooks/use-chat-engine';
import { useTranslation } from '@/i18n/client';

const INSTALLED_SKILL_REGEX = /Done! Skill '([^']+)' is now available/g;

interface SkillFinderChatProps {
  skillFinderId: string;
  sessionId: string;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  isRunning: boolean;
  setIsRunning: React.Dispatch<React.SetStateAction<boolean>>;
}

const EXAMPLE_PROMPTS = [
  'Find skills for converting PDF documents',
  'Show me data analysis skills',
  'I need a skill for generating posters from papers',
  'Search for web scraping skills',
];

function detectInstalledSkills(messages: ChatMessage[]): string[] {
  const skills = new Set<string>();
  for (const msg of messages) {
    if (!msg.streamEvents) continue;
    for (const evt of msg.streamEvents) {
      if (evt.type === 'tool_result' && evt.data) {
        const text = typeof evt.data.toolResult === 'string' ? evt.data.toolResult : '';
        const matches = Array.from(text.matchAll(INSTALLED_SKILL_REGEX));
        for (const match of matches) {
          skills.add(match[1]);
        }
      }
    }
  }
  return Array.from(skills);
}

export function SkillFinderChat({
  skillFinderId,
  sessionId,
  messages,
  setMessages,
  isRunning,
  setIsRunning,
}: SkillFinderChatProps) {
  const { t } = useTranslation('skills');
  const { t: tc } = useTranslation('chat');

  const [installedSkills, setInstalledSkills] = useState<string[]>([]);

  // Configuration
  const [showConfig, setShowConfig] = useState(false);
  const [maxTurns, setMaxTurns] = useState(30);
  const [selectedModelProvider, setSelectedModelProvider] = useState<string | null>('kimi');
  const [selectedModelName, setSelectedModelName] = useState<string | null>('kimi-k2.5');

  // Stable refs
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const isRunningRef = useRef(isRunning);
  isRunningRef.current = isRunning;
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // Auto-submit via example chip
  const pendingSubmitRef = useRef(false);

  // Fetch available models
  const { data: modelsData } = useQuery({
    queryKey: ['models-providers'],
    queryFn: () => modelsApi.listProviders(),
  });
  const modelProviders = modelsData?.providers || [];

  // Stable callbacks for messageAdapter
  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => [...prev, msg]);
  }, [setMessages]);

  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(m => (m.id === id ? { ...m, ...updates } : m)));
  }, [setMessages]);

  const removeMessages = useCallback((ids: string[]) => {
    setMessages(prev => prev.filter(m => !ids.includes(m.id)));
  }, [setMessages]);

  // Chat engine
  const engine = useChatEngine({
    messageAdapter: {
      getMessages: () => messagesRef.current,
      addMessage,
      updateMessage,
      removeMessages,
      getIsRunning: () => isRunningRef.current,
      setIsRunning,
      getUploadedFiles: () => [],
      clearUploadedFiles: () => {},
      addUploadedFile: () => {},
      removeUploadedFile: () => {},
    },
    streamAdapter: {
      runStream: async (request, agentFiles, onEvent, signal) => {
        await agentApi.runStream(
          {
            request,
            session_id: sessionIdRef.current,
            agent_id: skillFinderId,
            max_turns: maxTurns,
            model_provider: selectedModelProvider || undefined,
            model_name: selectedModelName || undefined,
            uploaded_files: agentFiles,
          },
          (event: StreamEvent) => {
            // Detect installed skills from tool_result events
            if (event.event_type === 'tool_result' && typeof event.tool_result === 'string') {
              const streamMatches = Array.from(event.tool_result.matchAll(INSTALLED_SKILL_REGEX));
              for (const match of streamMatches) {
                setInstalledSkills(prev =>
                  prev.includes(match[1]) ? prev : [...prev, match[1]]
                );
              }
            }
            onEvent(event);
          },
          signal
        );
      },
      steer: async (traceId, message) => {
        await agentApi.steerAgent(traceId, message);
      },
    },
  });

  // Re-detect installed skills when messages change (e.g. session restore)
  useEffect(() => {
    const detected = detectInstalledSkills(messages);
    if (detected.length > 0) {
      setInstalledSkills(detected);
    } else {
      setInstalledSkills([]);
    }
  }, [messages]);

  // Auto-scroll to bottom
  useEffect(() => {
    engine.messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, engine.streamingContent]);

  // Handle example chip click
  const handleExampleClick = useCallback((prompt: string) => {
    engine.setInput(prompt);
    pendingSubmitRef.current = true;
  }, [engine]);

  // Auto-submit after input is set
  useEffect(() => {
    if (pendingSubmitRef.current && engine.input.trim()) {
      pendingSubmitRef.current = false;
      engine.handleSubmit();
    }
  }, [engine.input]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Configuration Toggle */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Search className="h-4 w-4" />
          <span>{t('find.title')}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowConfig(!showConfig)}
          className="gap-1"
        >
          <Settings2 className="h-4 w-4" />
          {showConfig ? t('find.hideConfig') : t('find.showConfig')}
        </Button>
      </div>

      {/* Configuration Panel */}
      {showConfig && (
        <div className="px-4 py-3 border-b bg-muted/20 space-y-3 shrink-0">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="model" className="text-xs">{t('find.modelLabel')}</Label>
              <ModelSelect
                value={null}
                modelProvider={selectedModelProvider}
                modelName={selectedModelName}
                onChange={(p, m) => { setSelectedModelProvider(p); setSelectedModelName(m); }}
                providers={modelProviders}
                placeholder="Default"
                aria-label={t('find.modelLabel')}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="max-turns" className="text-xs">{t('find.maxTurns')}</Label>
              <Input
                id="max-turns"
                type="number"
                min={1}
                max={60000}
                value={maxTurns}
                onChange={(e) => setMaxTurns(parseInt(e.target.value) || 30)}
                className="h-9"
              />
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground">
            <div className="mx-auto mb-5 h-14 w-14 rounded-2xl bg-muted flex items-center justify-center">
              <Search className="h-7 w-7 opacity-50" />
            </div>
            <p className="font-medium text-lg text-foreground">{t('find.emptyTitle')}</p>
            <p className="text-sm mt-2 max-w-md mx-auto">{t('find.emptyDescription')}</p>
            <div className="flex flex-wrap justify-center gap-2 mt-6 max-w-lg mx-auto">
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleExampleClick(prompt)}
                  disabled={isRunning}
                  className="px-3 py-1.5 text-sm rounded-full border bg-background hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div key={message.id} className="max-w-4xl mx-auto">
              <ChatMessageItem
                message={message}
                streamingContent={engine.streamingMessageId === message.id ? engine.streamingContent : undefined}
                streamingEvents={engine.streamingMessageId === message.id ? engine.streamingEvents : undefined}
                streamingOutputFiles={engine.streamingMessageId === message.id ? engine.currentOutputFiles : undefined}
                onAskUserRespond={engine.handleRespond}
              />
            </div>
          ))
        )}
        <div ref={engine.messagesEndRef} />
      </div>

      {/* Installed Skills Banner */}
      {installedSkills.length > 0 && (
        <div className="bg-green-50 dark:bg-green-950/30 border-t border-green-200 dark:border-green-800 p-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0" />
            <span className="text-sm font-medium text-green-700 dark:text-green-400">
              {t('find.skillsInstalled')}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {installedSkills.map((name) => (
              <Link key={name} href={`/skills/${name}`}>
                <Button size="sm" variant="outline" className="border-green-300 dark:border-green-700 text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/50">
                  {name}
                </Button>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t shrink-0">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <Textarea
              value={engine.input}
              onChange={(e) => engine.setInput(e.target.value)}
              onKeyDown={engine.handleKeyDown}
              placeholder={t('find.inputPlaceholder')}
              className="min-h-[80px] resize-none"
              aria-label={t('find.inputPlaceholder')}
            />
          </div>
          <div className="flex justify-between items-center mt-2">
            <span className="text-xs text-muted-foreground hidden sm:inline">{tc('enterToSend')}</span>
            {isRunning ? (
              <div className="flex items-center gap-2">
                <Button onClick={engine.handleStop} variant="destructive" size="sm">
                  <Square className="h-4 w-4 mr-1" />{tc('stop')}
                </Button>
                <Button onClick={() => engine.handleSubmit()} disabled={!engine.input.trim()} size="sm">
                  {tc('send')}
                </Button>
              </div>
            ) : (
              <Button onClick={() => engine.handleSubmit()} disabled={!engine.input.trim()}>
                {tc('send')}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Bot, CheckCircle2, Settings2, Square, Paperclip, X } from 'lucide-react';
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

interface AgentBuilderChatProps {
  agentBuilderId: string;
  sessionId: string;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  isRunning: boolean;
  setIsRunning: React.Dispatch<React.SetStateAction<boolean>>;
}

export function AgentBuilderChat({
  agentBuilderId,
  sessionId,
  messages,
  setMessages,
  isRunning,
  setIsRunning,
}: AgentBuilderChatProps) {
  const router = useRouter();
  const { t } = useTranslation('agents');
  const { t: tc } = useTranslation('chat');

  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // Configuration
  const [showConfig, setShowConfig] = useState(true);
  const [maxTurns, setMaxTurns] = useState(60);
  const [selectedModelProvider, setSelectedModelProvider] = useState<string | null>('kimi');
  const [selectedModelName, setSelectedModelName] = useState<string | null>('kimi-k2.5');

  // Stable refs
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const isRunningRef = useRef(isRunning);
  isRunningRef.current = isRunning;
  const uploadedFilesRef = useRef(uploadedFiles);
  uploadedFilesRef.current = uploadedFiles;
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

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
      getUploadedFiles: () => uploadedFilesRef.current,
      clearUploadedFiles: () => setUploadedFiles([]),
      addUploadedFile: (file) => setUploadedFiles(prev => [...prev, file]),
      removeUploadedFile: (fileId) => setUploadedFiles(prev => prev.filter(f => f.file_id !== fileId)),
    },
    streamAdapter: {
      runStream: async (request, agentFiles, onEvent, signal) => {
        await agentApi.runStream(
          {
            request,
            session_id: sessionIdRef.current,
            agent_id: agentBuilderId,
            max_turns: maxTurns,
            model_provider: selectedModelProvider || undefined,
            model_name: selectedModelName || undefined,
            uploaded_files: agentFiles,
          },
          (event: StreamEvent) => {
            // Check for created agent
            if (event.event_type === 'complete' && event.answer) {
              const agentIdMatch = event.answer.match(/Agent.*?ID[:\s]+([a-f0-9-]{36})/i);
              if (agentIdMatch) {
                setCreatedAgentId(agentIdMatch[1]);
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

  // Auto-scroll to bottom
  useEffect(() => {
    engine.messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, engine.streamingContent]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Configuration Toggle */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30 shrink-0">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Bot className="h-4 w-4" />
          <span>{t('create.builderTitle')}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowConfig(!showConfig)}
          className="gap-1"
        >
          <Settings2 className="h-4 w-4" />
          {showConfig ? t('create.hideConfig') : t('create.showConfig')}
        </Button>
      </div>

      {/* Configuration Panel */}
      {showConfig && (
        <div className="px-4 py-3 border-b bg-muted/20 space-y-3 shrink-0">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label htmlFor="model" className="text-xs">{t('create.modelLabel')}</Label>
              <ModelSelect
                value={null}
                modelProvider={selectedModelProvider}
                modelName={selectedModelName}
                onChange={(p, m) => { setSelectedModelProvider(p); setSelectedModelName(m); }}
                providers={modelProviders}
                placeholder={t('create.modelDefault')}
                aria-label={t('create.modelLabel')}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="max-turns" className="text-xs">{t('create.maxTurns')}</Label>
              <Input
                id="max-turns"
                type="number"
                min={1}
                max={60000}
                value={maxTurns}
                onChange={(e) => setMaxTurns(parseInt(e.target.value) || 60)}
                className="h-9"
              />
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">{t('create.describeAgent')}</p>
            <p className="text-sm mt-2">{t('create.describeAgentHint')}</p>
          </div>
        ) : (
          messages.map((message, idx) => (
            <div key={message.id} className="max-w-4xl mx-auto">
              <ChatMessageItem
                message={message}
                streamingContent={engine.streamingMessageId === message.id ? engine.streamingContent : undefined}
                streamingEvents={engine.streamingMessageId === message.id ? engine.streamingEvents : undefined}
                streamingOutputFiles={engine.streamingMessageId === message.id ? engine.currentOutputFiles : undefined}
                onAskUserRespond={engine.handleRespond}
                askUserAnswer={message.role === 'assistant' && messages[idx + 1]?.role === 'user' ? messages[idx + 1].content : undefined}
              />
            </div>
          ))
        )}
        <div ref={engine.messagesEndRef} />
      </div>

      {/* Created Agent Banner */}
      {createdAgentId && (
        <div className="bg-green-50 dark:bg-green-950/30 border-t border-green-200 dark:border-green-800 p-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <span className="text-sm font-medium text-green-700 dark:text-green-400">
              {t('create.agentCreated')}
            </span>
          </div>
          <Button
            size="sm"
            onClick={() => router.push(`/agents/${createdAgentId}`)}
          >
            {t('create.viewAgent')}
          </Button>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t shrink-0">
        <div className="max-w-4xl mx-auto">
          {uploadedFiles.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {uploadedFiles.map((file) => (
                <div key={file.file_id} className="flex items-center gap-1 bg-muted rounded px-2 py-1 text-xs">
                  <Paperclip className="h-3 w-3" />
                  <span className="max-w-[150px] truncate" title={file.filename}>{file.filename}</span>
                  <button onClick={() => engine.handleRemoveFile(file.file_id)} className="hover:text-destructive ml-1">
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <Textarea
              value={engine.input}
              onChange={(e) => engine.setInput(e.target.value)}
              onKeyDown={engine.handleKeyDown}
              placeholder={tc('placeholder')}
              className="min-h-[80px] resize-none"
              aria-label={tc('placeholder')}
            />
          </div>
          <div className="flex justify-between items-center mt-2">
            <div className="flex items-center gap-2">
              <input ref={engine.fileInputRef} type="file" multiple onChange={engine.handleFileUpload} className="hidden" disabled={isRunning || engine.isUploading} />
              <Button variant="outline" size="sm" onClick={() => engine.fileInputRef.current?.click()} disabled={isRunning || engine.isUploading}>
                <Paperclip className="h-4 w-4 mr-1" />
                {engine.isUploading ? tc('files.uploading') : tc('attach')}
              </Button>
              <span className="text-xs text-muted-foreground hidden sm:inline">{tc('enterToSend')}</span>
            </div>
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

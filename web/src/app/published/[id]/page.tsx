"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Paperclip, X, Square, Bot, Loader2, MessageSquarePlus, PanelLeft, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { publishedAgentApi } from "@/lib/api";
import type { StreamEvent, UploadedFile } from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import { ChatMessageItem } from "@/components/chat/chat-message";
import { useChatEngine } from "@/hooks/use-chat-engine";
import { useTranslation } from "@/i18n/client";
import { generateUUID } from "@/lib/utils";
import { toast } from "sonner";
import { sessionMessagesToChatMessages } from "@/lib/session-utils";
import { SessionSidebar } from "@/components/published/session-sidebar";
import { useQueryClient } from "@tanstack/react-query";
import { publishedSessionKeys } from "@/hooks/use-published-sessions";

type LocalMessage = ChatMessage;

function SessionIdBadge({ sessionId, label, copiedText }: { sessionId: string; label: string; copiedText: string }) {
  const [copied, setCopied] = useState(false);
  const shortId = `${sessionId.slice(0, 4)}...${sessionId.slice(-4)}`;

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(sessionId).then(() => {
      setCopied(true);
      toast.success(copiedText);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [sessionId, copiedText]);

  return (
    <button
      onClick={handleCopy}
      className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono text-muted-foreground bg-muted/50 hover:bg-muted transition-colors cursor-pointer shrink-0"
      title={`${label}: ${sessionId}`}
      aria-label={`${label}: ${sessionId}`}
    >
      <span className="text-muted-foreground/70">{label}:</span>
      <span>{shortId}</span>
      {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 opacity-50" />}
    </button>
  );
}

function getSessionStorageKey(agentId: string): string {
  return `published-session-${agentId}`;
}

function getOrCreateSessionId(agentId: string): string {
  if (typeof window === 'undefined') return generateUUID();
  const key = getSessionStorageKey(agentId);
  const existing = sessionStorage.getItem(key);
  if (existing) return existing;
  const id = generateUUID();
  sessionStorage.setItem(key, id);
  return id;
}

export default function PublishedChatPage() {
  const { t } = useTranslation('chat');
  const params = useParams();
  const agentId = params.id as string;
  const queryClient = useQueryClient();

  // Agent info
  const [agentName, setAgentName] = useState<string | null>(null);
  const [agentDescription, setAgentDescription] = useState<string | null>(null);
  const [apiResponseMode, setApiResponseMode] = useState<'streaming' | 'non_streaming' | null>(null);
  const [loadingInfo, setLoadingInfo] = useState(true);
  const [infoError, setInfoError] = useState<string | null>(null);

  // Session
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId(agentId));
  const [restoringSession, setRestoringSession] = useState(false);

  // Chat state (local)
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // Mobile sidebar
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Stable refs for sessionId and apiResponseMode (used in adapters)
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const apiResponseModeRef = useRef(apiResponseMode);
  apiResponseModeRef.current = apiResponseMode;
  const isRunningRef = useRef(isRunning);
  isRunningRef.current = isRunning;
  const uploadedFilesRef = useRef(uploadedFiles);
  uploadedFilesRef.current = uploadedFiles;
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const addMessage = useCallback((msg: LocalMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateMessage = useCallback((id: string, updates: Partial<LocalMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...updates } : m)));
  }, []);

  const removeMessages = useCallback((ids: string[]) => {
    setMessages((prev) => prev.filter((m) => !ids.includes(m.id)));
  }, []);

  // ── Shared chat engine ──
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
      addUploadedFile: (file) => setUploadedFiles((prev) => [...prev, file]),
      removeUploadedFile: (fileId) => setUploadedFiles((prev) => prev.filter((f) => f.file_id !== fileId)),
    },
    streamAdapter: {
      runStream: async (request, agentFiles, onEvent, signal) => {
        await publishedAgentApi.chatStream(
          agentId,
          { request, session_id: sessionIdRef.current, uploaded_files: agentFiles },
          (event: StreamEvent) => onEvent(event),
          signal
        );
      },
      runSync: async (request, agentFiles) => {
        return await publishedAgentApi.chatSync(agentId, {
          request, session_id: sessionIdRef.current, uploaded_files: agentFiles,
        });
      },
      steer: async (traceId, message) => {
        await publishedAgentApi.steerAgent(agentId, traceId, message);
      },
    },
    responseMode: (apiResponseMode === 'non_streaming') ? 'non_streaming' : 'streaming',
  });

  // Load agent info + restore session
  useEffect(() => {
    async function loadInfo() {
      try {
        const info = await publishedAgentApi.getInfo(agentId);
        setAgentName(info.name);
        setAgentDescription(info.description);
        setApiResponseMode(info.api_response_mode);
      } catch {
        setInfoError(t('published.notAvailable'));
        setLoadingInfo(false);
        return;
      }

      setRestoringSession(true);
      try {
        const sessionData = await publishedAgentApi.getSession(agentId, sessionId);
        if (sessionData.messages.length > 0) {
          const restoredMessages = sessionMessagesToChatMessages(sessionData.messages);
          setMessages(restoredMessages);
        }
      } catch {
        // Session not found — first visit
      } finally {
        setRestoringSession(false);
      }

      setLoadingInfo(false);
    }
    loadInfo();
  }, [agentId]);

  // Auto-scroll
  useEffect(() => {
    engine.messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, engine.streamingContent]);

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
    sessionStorage.setItem(getSessionStorageKey(agentId), newId);
    setSessionId(newId);
    setMessages([]);
    setUploadedFiles([]);
    setMobileSidebarOpen(false);
  }, [agentId]);

  const handleSessionSwitch = useCallback(async (newSessionId: string) => {
    if (newSessionId === sessionId || isRunning) return;

    sessionStorage.setItem(getSessionStorageKey(agentId), newSessionId);
    setSessionId(newSessionId);
    setMessages([]);
    setUploadedFiles([]);
    setMobileSidebarOpen(false);

    try {
      const data = await publishedAgentApi.getSession(agentId, newSessionId);
      if (data.messages.length > 0) {
        setMessages(sessionMessagesToChatMessages(data.messages));
      }
    } catch {
      // First visit or not found
    }
  }, [agentId, sessionId, isRunning]);

  if (loadingInfo || restoringSession) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (infoError) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h1 className="text-xl font-semibold mb-2">{t('agentNotAvailable')}</h1>
          <p className="text-muted-foreground">{infoError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      {/* Desktop sidebar */}
      <div className="w-[260px] shrink-0 hidden md:flex flex-col border-r bg-muted/30">
        <SessionSidebar
          agentId={agentId}
          activeSessionId={sessionId}
          onSessionSelect={handleSessionSwitch}
          onNewChat={handleNewChat}
          isRunning={isRunning}
        />
      </div>

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileSidebarOpen(false)}
          />
          {/* Sidebar panel */}
          <div className="absolute inset-y-0 left-0 w-[280px] bg-background border-r shadow-xl flex flex-col animate-in slide-in-from-left duration-200">
            <SessionSidebar
              agentId={agentId}
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
        {/* Header */}
        <div className="border-b px-4 sm:px-6 py-4 flex items-center gap-3 shrink-0">
          {/* Mobile sidebar toggle */}
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden p-1.5"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <PanelLeft className="h-5 w-5" />
          </Button>
          <Bot className="h-6 w-6 text-primary" />
          <div className="flex-1 min-w-0">
            <h1 className="font-semibold text-lg">{agentName}</h1>
            {agentDescription && <p className="text-sm text-muted-foreground truncate">{agentDescription}</p>}
          </div>
          <SessionIdBadge sessionId={sessionId} label={t('published.sessionId')} copiedText={t('published.sessionIdCopied')} />
          <Button variant="outline" size="sm" onClick={handleNewChat} disabled={isRunning} title={t('newChat')}>
            <MessageSquarePlus className="h-4 w-4 sm:mr-1" />
            <span className="hidden sm:inline">{t('newChat')}</span>
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-muted-foreground py-16">
              <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">{t('startConversation')}</p>
              <p className="text-sm mt-2">{t('published.typeToBegin')}</p>
            </div>
          ) : (
            messages.map((message) => (
              <div key={message.id} className="max-w-4xl mx-auto">
                <ChatMessageItem
                  message={message}
                  streamingContent={message.id === engine.streamingMessageId ? engine.streamingContent : null}
                  streamingEvents={message.id === engine.streamingMessageId ? engine.streamingEvents : undefined}
                  streamingOutputFiles={message.id === engine.streamingMessageId ? engine.currentOutputFiles : undefined}
                  hideTraceLink
                />
              </div>
            ))
          )}
          <div ref={engine.messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t px-4 sm:px-6 py-4 shrink-0">
          <div className="max-w-4xl mx-auto">
            {uploadedFiles.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {uploadedFiles.map((file) => (
                  <div key={file.file_id} className="flex items-center gap-1 bg-muted rounded px-2 py-1 text-xs">
                    <Paperclip className="h-3 w-3" />
                    <span className="max-w-[150px] truncate" title={file.filename}>{file.filename}</span>
                    <button onClick={() => engine.handleRemoveFile(file.file_id)} className="hover:text-destructive ml-1" title={t('files.remove')}>
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
                placeholder={t('placeholder')}
                className="min-h-[80px] resize-none"
                aria-label={t('placeholder')}
              />
            </div>
            <div className="flex justify-between items-center mt-2">
              <div className="flex items-center gap-2">
                <input ref={engine.fileInputRef} type="file" multiple onChange={engine.handleFileUpload} className="hidden" disabled={isRunning || engine.isUploading} />
                <Button variant="outline" size="sm" onClick={() => engine.fileInputRef.current?.click()} disabled={isRunning || engine.isUploading} title={t('files.upload')}>
                  <Paperclip className="h-4 w-4 mr-1" />
                  {engine.isUploading ? t('files.uploading') : t('attach')}
                </Button>
                <span className="text-xs text-muted-foreground hidden sm:inline">{t('enterToSend')}</span>
              </div>
              {isRunning ? (
                <div className="flex items-center gap-2">
                  <Button onClick={engine.handleStop} variant="destructive" size="sm">
                    <Square className="h-4 w-4 mr-1" />{t('stop')}
                  </Button>
                  <Button onClick={engine.handleSubmit} disabled={!engine.input.trim()} size="sm">
                    {t('send')}
                  </Button>
                </div>
              ) : (
                <Button onClick={engine.handleSubmit} disabled={!engine.input.trim()}>{t('send')}</Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

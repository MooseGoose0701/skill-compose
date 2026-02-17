"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Paperclip, X, Square, Bot, Loader2, MessageSquarePlus, Navigation } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { publishedAgentApi } from "@/lib/api";
import type { StreamEvent, UploadedFile } from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import { ChatMessageItem } from "@/components/chat/chat-message";
import { useChatEngine } from "@/hooks/use-chat-engine";
import { useTranslation } from "@/i18n/client";

type LocalMessage = ChatMessage;

function getSessionStorageKey(agentId: string): string {
  return `published-session-${agentId}`;
}

function getOrCreateSessionId(agentId: string): string {
  if (typeof window === 'undefined') return crypto.randomUUID();
  const key = getSessionStorageKey(agentId);
  const existing = sessionStorage.getItem(key);
  if (existing) return existing;
  const id = crypto.randomUUID();
  sessionStorage.setItem(key, id);
  return id;
}

export default function PublishedChatPage() {
  const { t } = useTranslation('chat');
  const params = useParams();
  const agentId = params.id as string;

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
          const restoredMessages: LocalMessage[] = [];
          for (const msg of sessionData.messages) {
            if (msg.role === "user") {
              if (typeof msg.content === "string") {
                restoredMessages.push({
                  id: `restored-${restoredMessages.length}`,
                  role: "user",
                  content: msg.content,
                  timestamp: Date.now(),
                });
              }
            } else if (msg.role === "assistant") {
              let text = "";
              if (typeof msg.content === "string") {
                text = msg.content;
              } else if (Array.isArray(msg.content)) {
                text = msg.content
                  .filter((b: Record<string, unknown>) => b.type === "text")
                  .map((b: Record<string, unknown>) => b.text as string)
                  .join("\n");
              }
              if (text.trim()) {
                restoredMessages.push({
                  id: `restored-${restoredMessages.length}`,
                  role: "assistant",
                  content: text,
                  rawAnswer: text,
                  timestamp: Date.now(),
                });
              }
            }
          }
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

  const handleNewChat = () => {
    const newId = crypto.randomUUID();
    sessionStorage.setItem(getSessionStorageKey(agentId), newId);
    setSessionId(newId);
    setMessages([]);
    setUploadedFiles([]);
  };

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
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b px-6 py-4 flex items-center gap-3 shrink-0">
        <Bot className="h-6 w-6 text-primary" />
        <div className="flex-1">
          <h1 className="font-semibold text-lg">{agentName}</h1>
          {agentDescription && <p className="text-sm text-muted-foreground">{agentDescription}</p>}
        </div>
        <Button variant="outline" size="sm" onClick={handleNewChat} disabled={isRunning} title={t('newChat')}>
          <MessageSquarePlus className="h-4 w-4 mr-1" />
          {t('newChat')}
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-6 space-y-4">
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
      <div className="border-t px-6 py-4 shrink-0">
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
              placeholder={isRunning ? t('steering.placeholder') : t('placeholder')}
              className="min-h-[80px] resize-none"
            />
          </div>
          <div className="flex justify-between items-center mt-2">
            <div className="flex items-center gap-2">
              <input ref={engine.fileInputRef} type="file" multiple onChange={engine.handleFileUpload} className="hidden" disabled={isRunning || engine.isUploading} />
              <Button variant="outline" size="sm" onClick={() => engine.fileInputRef.current?.click()} disabled={isRunning || engine.isUploading} title={t('files.upload')}>
                <Paperclip className="h-4 w-4 mr-1" />
                {engine.isUploading ? t('files.uploading') : t('attach')}
              </Button>
              <span className="text-xs text-muted-foreground">{t('enterToSend')}</span>
            </div>
            {isRunning ? (
              <div className="flex items-center gap-2">
                <Button onClick={engine.handleStop} variant="destructive" size="sm">
                  <Square className="h-4 w-4 mr-1" />{t('stop')}
                </Button>
                <Button onClick={engine.handleSubmit} disabled={!engine.input.trim()} size="sm">
                  <Navigation className="h-4 w-4 mr-1" />{t('steering.button')}
                </Button>
              </div>
            ) : (
              <Button onClick={engine.handleSubmit} disabled={!engine.input.trim()}>{t('send')}</Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

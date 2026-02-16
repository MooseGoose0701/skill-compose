"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { flushSync } from "react-dom";
import { Paperclip, X, Square, Bot, Loader2, MessageSquarePlus, Navigation } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { publishedAgentApi, filesApi } from "@/lib/api";
import type { StreamEvent, OutputFileInfo, UploadedFile } from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import { ChatMessageItem } from "@/components/chat/chat-message";
import type { StreamEventRecord } from "@/types/stream-events";
import { handleStreamEvent, serializeEventsToText } from "@/lib/stream-utils";
import { toast } from "sonner";

type LocalMessage = ChatMessage;

function getSessionStorageKey(agentId: string): string {
  return `published-session-${agentId}`;
}

function generateUUID(): string {
  return crypto.randomUUID();
}

/** Read or create a session ID for this agent tab */
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
  const params = useParams();
  const agentId = params.id as string;

  // Agent info
  const [agentName, setAgentName] = useState<string | null>(null);
  const [agentDescription, setAgentDescription] = useState<string | null>(null);
  const [apiResponseMode, setApiResponseMode] = useState<'streaming' | 'non_streaming' | null>(null);
  const [loadingInfo, setLoadingInfo] = useState(true);
  const [infoError, setInfoError] = useState<string | null>(null);

  // Session state — always has a value (read or generated on mount)
  const [sessionId, setSessionId] = useState<string>(() => getOrCreateSessionId(agentId));
  const [restoringSession, setRestoringSession] = useState(false);

  // Chat state (local, not Zustand)
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [streamingEvents, setStreamingEvents] = useState<StreamEventRecord[]>([]);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [currentOutputFiles, setCurrentOutputFiles] = useState<OutputFileInfo[]>([]);

  // File upload state
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentTraceIdRef = useRef<string | null>(null);

  // Load agent info + restore session
  useEffect(() => {
    async function loadInfo() {
      try {
        const info = await publishedAgentApi.getInfo(agentId);
        setAgentName(info.name);
        setAgentDescription(info.description);
        setApiResponseMode(info.api_response_mode);
      } catch {
        setInfoError("This agent is not available.");
        setLoadingInfo(false);
        return;
      }

      // Try to restore session messages from server
      setRestoringSession(true);
      try {
        const sessionData = await publishedAgentApi.getSession(agentId, sessionId);
        if (sessionData.messages.length > 0) {
          // Filter and extract displayable messages from full conversation
          // (which may include tool_use/tool_result blocks)
          const restoredMessages: LocalMessage[] = [];
          for (const msg of sessionData.messages) {
            if (msg.role === "user") {
              // Only show user messages with string content (skip tool_result arrays)
              if (typeof msg.content === "string") {
                restoredMessages.push({
                  id: `restored-${restoredMessages.length}`,
                  role: "user",
                  content: msg.content,
                  timestamp: Date.now(),
                });
              }
            } else if (msg.role === "assistant") {
              // Extract text from assistant messages (may be string or content blocks array)
              let text = "";
              if (typeof msg.content === "string") {
                text = msg.content;
              } else if (Array.isArray(msg.content)) {
                text = msg.content
                  .filter((b: Record<string, unknown>) => b.type === "text")
                  .map((b: Record<string, unknown>) => b.text as string)
                  .join("\n");
              }
              // Only add if there's actual text (skip tool-only assistant turns)
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
        // Session not found on server (first visit) — that's fine, nothing to restore
      } finally {
        setRestoringSession(false);
      }

      setLoadingInfo(false);
    }
    loadInfo();
  }, [agentId]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const addMessage = useCallback((msg: LocalMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateMessage = useCallback((id: string, updates: Partial<LocalMessage>) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg))
    );
  }, []);

  const handleNewChat = () => {
    const newId = generateUUID();
    sessionStorage.setItem(getSessionStorageKey(agentId), newId);
    setSessionId(newId);
    setMessages([]);
    setInput("");
    setStreamingContent(null);
    setStreamingEvents([]);
    setStreamingMessageId(null);
    setCurrentOutputFiles([]);
    setUploadedFiles([]);
  };

  const handleSteer = async (message: string) => {
    const traceId = currentTraceIdRef.current;
    if (!traceId) return;
    try {
      await publishedAgentApi.steerAgent(agentId, traceId, message);
      setInput("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send steering message");
    }
  };

  const handleSubmit = async () => {
    if (!input.trim()) return;

    // Steering mode
    if (isRunning && currentTraceIdRef.current) {
      await handleSteer(input.trim());
      return;
    }

    if (isRunning) return;

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // Capture uploaded files before clearing
    const agentFiles = uploadedFiles.length > 0
      ? uploadedFiles.map((f) => ({
          file_id: f.file_id,
          filename: f.filename,
          path: f.path,
          content_type: f.content_type,
        }))
      : undefined;

    const userMessage: LocalMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
      attachedFiles: uploadedFiles.length > 0
        ? uploadedFiles.map((f) => ({ file_id: f.file_id, filename: f.filename }))
        : undefined,
    };

    const loadingMessageId = (Date.now() + 1).toString();
    const loadingMessage: LocalMessage = {
      id: loadingMessageId,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      isLoading: true,
    };

    addMessage(userMessage);
    addMessage(loadingMessage);
    setInput("");
    setUploadedFiles([]);
    setIsRunning(true);
    setStreamingMessageId(loadingMessageId);
    setStreamingContent("");
    setStreamingEvents([]);
    setCurrentOutputFiles([]);

    try {

      // Non-streaming mode: use sync endpoint
      if (apiResponseMode === 'non_streaming') {
        const result = await publishedAgentApi.chatSync(agentId, {
          request: userMessage.content,
          session_id: sessionId,
          uploaded_files: agentFiles,
        });

        // Build structured events from steps
        const events: StreamEventRecord[] = [];
        let eventId = 0;
        const now = Date.now();

        if (result.steps && result.steps.length > 0) {
          for (const step of result.steps) {
            if (step.tool_name) {
              // Tool call event
              events.push({
                id: `sync-${eventId++}`,
                type: 'tool_call',
                timestamp: now,
                data: {
                  toolName: step.tool_name,
                  toolInput: step.tool_input as Record<string, unknown> | undefined,
                },
              });
              // Tool result event (content is the result)
              if (step.content) {
                events.push({
                  id: `sync-${eventId++}`,
                  type: 'tool_result',
                  timestamp: now,
                  data: {
                    toolName: step.tool_name,
                    toolResult: step.content,
                    success: true,
                  },
                });
              }
            } else if (step.content) {
              // Assistant thinking
              events.push({
                id: `sync-${eventId++}`,
                type: 'assistant',
                timestamp: now,
                data: {
                  content: step.content,
                },
              });
            }
          }
        }

        // Complete event
        events.push({
          id: `sync-${eventId++}`,
          type: 'complete',
          timestamp: now,
          data: {
            success: result.success,
            answer: result.answer,
            totalTurns: result.total_turns,
          },
        });

        // Error event if there was an error
        if (result.error) {
          events.push({
            id: `sync-${eventId++}`,
            type: 'error',
            timestamp: now,
            data: {
              message: result.error,
            },
          });
        }

        updateMessage(loadingMessageId, {
          content: serializeEventsToText(events),
          streamEvents: events,
          rawAnswer: result.answer || undefined,
          isLoading: false,
          traceId: result.trace_id,
          error: result.error,
        });
      } else {
        // Streaming mode: use SSE endpoint
        const events: StreamEventRecord[] = [];
        let finalAnswer = "";
        let traceId: string | undefined;
        let hasError = false;
        let errorMessage = "";
        let isComplete = false;
        const outputFiles: OutputFileInfo[] = [];

        await publishedAgentApi.chatStream(
          agentId,
          {
            request: userMessage.content,
            session_id: sessionId,
            uploaded_files: agentFiles,
          },
          (event: StreamEvent) => {
            // Accumulate text_delta into assistant records, or map other events
            handleStreamEvent(event, events);

            // Handle special cases
            switch (event.event_type) {
              case "run_started":
                traceId = event.trace_id;
                currentTraceIdRef.current = traceId || null;
                flushSync(() => {
                  updateMessage(loadingMessageId, { traceId });
                });
                break;
              case "complete":
                if (isComplete) break;
                isComplete = true;
                finalAnswer = event.answer || "";
                break;
              case "error":
                hasError = true;
                errorMessage = event.message || event.error || "Unknown error";
                break;
              case "trace_saved":
                traceId = event.trace_id;
                break;
              case "output_file":
                if (event.file_id && event.filename && event.download_url) {
                  const fileInfo: OutputFileInfo = {
                    file_id: event.file_id,
                    filename: event.filename,
                    size: event.size || 0,
                    content_type: event.content_type || "application/octet-stream",
                    download_url: event.download_url,
                    description: event.description,
                  };
                  outputFiles.push(fileInfo);
                  flushSync(() => {
                    setCurrentOutputFiles([...outputFiles]);
                  });
                }
                break;
            }

            flushSync(() => {
              setStreamingEvents([...events]);
              setStreamingContent(serializeEventsToText(events));
            });
          },
          abortController.signal
        );

        updateMessage(loadingMessageId, {
          content: serializeEventsToText(events),
          streamEvents: events,
          rawAnswer: finalAnswer || undefined,
          isLoading: false,
          traceId,
          error: hasError ? errorMessage : undefined,
          outputFiles: outputFiles.length > 0 ? outputFiles : undefined,
        });
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }
      updateMessage(loadingMessageId, {
        content: "Failed to run agent",
        isLoading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setIsRunning(false);
      setStreamingMessageId(null);
      setStreamingContent(null);
      setStreamingEvents([]);
      setCurrentOutputFiles([]);
      abortControllerRef.current = null;
      currentTraceIdRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleStop = () => {
    if (!isRunning || !abortControllerRef.current) return;
    abortControllerRef.current.abort();
    // Remove last two messages (user + loading)
    setMessages((prev) => prev.slice(0, -2));
    setIsRunning(false);
    setStreamingMessageId(null);
    setStreamingContent(null);
    setStreamingEvents([]);
    setCurrentOutputFiles([]);
    abortControllerRef.current = null;
    currentTraceIdRef.current = null;
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        const uploaded = await filesApi.upload(file);
        setUploadedFiles((prev) => [...prev, uploaded]);
      }
    } catch (err) {
      console.error("File upload failed:", err);
      toast.error(err instanceof Error ? err.message : "File upload failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveFile = async (fileId: string) => {
    try {
      await filesApi.delete(fileId);
    } catch {
      // Ignore server delete errors
    }
    setUploadedFiles((prev) => prev.filter((f) => f.file_id !== fileId));
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
          <h1 className="text-xl font-semibold mb-2">Agent Not Available</h1>
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
          {agentDescription && (
            <p className="text-sm text-muted-foreground">{agentDescription}</p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleNewChat}
          disabled={isRunning}
          title="Start new chat"
        >
          <MessageSquarePlus className="h-4 w-4 mr-1" />
          New Chat
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-16">
            <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg">Start a conversation</p>
            <p className="text-sm mt-2">Type a message below to begin.</p>
          </div>
        ) : (
          messages.map((message) => (
            <div key={message.id} className="max-w-3xl mx-auto">
              <ChatMessageItem
                message={message}
                streamingContent={message.id === streamingMessageId ? streamingContent : null}
                streamingEvents={message.id === streamingMessageId ? streamingEvents : undefined}
                streamingOutputFiles={message.id === streamingMessageId ? currentOutputFiles : undefined}
                hideTraceLink
              />
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t px-6 py-4 shrink-0">
        <div className="max-w-3xl mx-auto">
          {/* Uploaded Files Display */}
          {uploadedFiles.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {uploadedFiles.map((file) => (
                <div
                  key={file.file_id}
                  className="flex items-center gap-1 bg-muted rounded px-2 py-1 text-xs"
                >
                  <Paperclip className="h-3 w-3" />
                  <span className="max-w-[150px] truncate" title={file.filename}>
                    {file.filename}
                  </span>
                  <button
                    onClick={() => handleRemoveFile(file.file_id)}
                    className="hover:text-destructive ml-1"
                    title="Remove file"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isRunning ? "Steer the agent..." : "Type your message..."}
              className="min-h-[80px] resize-none"
            />
          </div>
          <div className="flex justify-between items-center mt-2">
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileUpload}
                className="hidden"
                disabled={isRunning || isUploading}
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={isRunning || isUploading}
                title="Upload files"
              >
                <Paperclip className="h-4 w-4 mr-1" />
                {isUploading ? "Uploading..." : "Attach"}
              </Button>
              <span className="text-xs text-muted-foreground">
                Enter to send
              </span>
            </div>
            {isRunning ? (
              <div className="flex items-center gap-2">
                <Button onClick={handleStop} variant="destructive" size="sm">
                  <Square className="h-4 w-4 mr-1" />
                  Stop
                </Button>
                <Button onClick={handleSubmit} disabled={!input.trim()} size="sm">
                  <Navigation className="h-4 w-4 mr-1" />
                  Steer
                </Button>
              </div>
            ) : (
              <Button onClick={handleSubmit} disabled={!input.trim()}>
                Send
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

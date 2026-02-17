"use client";

import React from "react";
import { flushSync } from "react-dom";
import { filesApi } from "@/lib/api";
import type { StreamEvent, OutputFileInfo, UploadedFile } from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import type { StreamEventRecord } from "@/types/stream-events";
import { handleStreamEvent, serializeEventsToText } from "@/lib/stream-utils";
import { toast } from "sonner";

// ── Adapter interfaces ────────────────────────────────────────────

/** How to get/set messages and running state */
export interface MessageAdapter {
  getMessages: () => ChatMessage[];
  addMessage: (msg: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  removeMessages: (ids: string[]) => void;
  getIsRunning: () => boolean;
  setIsRunning: (running: boolean) => void;
  getUploadedFiles: () => UploadedFile[];
  clearUploadedFiles: () => void;
  addUploadedFile: (file: UploadedFile) => void;
  removeUploadedFile: (fileId: string) => void;
}

/** How to call the streaming / sync API */
export interface StreamAdapter {
  runStream: (
    request: string,
    agentFiles: { file_id: string; filename: string; path: string; content_type: string }[] | undefined,
    onEvent: (event: StreamEvent) => void,
    signal: AbortSignal
  ) => Promise<void>;
  runSync?: (
    request: string,
    agentFiles: { file_id: string; filename: string; path: string; content_type: string }[] | undefined,
  ) => Promise<{
    success: boolean;
    answer: string;
    total_turns: number;
    steps: Array<{ role: string; content: string; tool_name?: string; tool_input?: unknown }>;
    error?: string;
    trace_id?: string;
    session_id?: string;
  }>;
  steer: (traceId: string, message: string) => Promise<void>;
}

export interface ChatEngineOptions {
  messageAdapter: MessageAdapter;
  streamAdapter: StreamAdapter;
  /** 'streaming' | 'non_streaming' — defaults to 'streaming' */
  responseMode?: 'streaming' | 'non_streaming';
  /** Called when session_id changes (e.g. from run_started event) */
  onSessionId?: (id: string) => void;
}

export interface ChatEngineReturn {
  input: string;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  handleSubmit: () => Promise<void>;
  handleStop: () => void;
  handleKeyDown: (e: React.KeyboardEvent) => void;
  handleFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleRemoveFile: (fileId: string) => Promise<void>;
  streamingContent: string | null;
  streamingEvents: StreamEventRecord[];
  streamingMessageId: string | null;
  currentOutputFiles: OutputFileInfo[];
  isUploading: boolean;
  fileInputRef: React.RefObject<HTMLInputElement>;
  messagesEndRef: React.RefObject<HTMLDivElement>;
}

// ── Hook implementation ───────────────────────────────────────────

export function useChatEngine(options: ChatEngineOptions): ChatEngineReturn {
  const { messageAdapter, streamAdapter, responseMode = 'streaming', onSessionId } = options;

  const [input, setInput] = React.useState("");
  const [streamingContent, setStreamingContent] = React.useState<string | null>(null);
  const [streamingEvents, setStreamingEvents] = React.useState<StreamEventRecord[]>([]);
  const [streamingMessageId, setStreamingMessageId] = React.useState<string | null>(null);
  const [currentOutputFiles, setCurrentOutputFiles] = React.useState<OutputFileInfo[]>([]);
  const [isUploading, setIsUploading] = React.useState(false);

  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const abortControllerRef = React.useRef<AbortController | null>(null);
  const currentRequestMessagesRef = React.useRef<string[]>([]);
  const currentTraceIdRef = React.useRef<string | null>(null);

  // Stable refs to avoid stale closures in callbacks
  const adapterRef = React.useRef(options);
  adapterRef.current = options;

  const handleSteer = React.useCallback(async (message: string) => {
    const traceId = currentTraceIdRef.current;
    if (!traceId) return;
    try {
      await adapterRef.current.streamAdapter.steer(traceId, message);
      setInput("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send steering message");
    }
  }, []);

  const handleSubmit = React.useCallback(async () => {
    if (!input.trim()) return;
    const { messageAdapter: ma, streamAdapter: sa, responseMode: rm = 'streaming', onSessionId: onSid } = adapterRef.current;

    // Steering mode: inject message into running agent
    if (ma.getIsRunning() && currentTraceIdRef.current) {
      await handleSteer(input.trim());
      return;
    }

    // Prevent concurrent runs
    if (ma.getIsRunning()) return;

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // Capture uploaded files before clearing
    const uploadedFiles = ma.getUploadedFiles();
    const agentFiles = uploadedFiles.length > 0
      ? uploadedFiles.map((f) => ({
          file_id: f.file_id,
          filename: f.filename,
          path: f.path,
          content_type: f.content_type,
        }))
      : undefined;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
      attachedFiles: uploadedFiles.length > 0
        ? uploadedFiles.map((f) => ({ file_id: f.file_id, filename: f.filename }))
        : undefined,
    };

    const loadingMessageId = (Date.now() + 1).toString();
    const loadingMessage: ChatMessage = {
      id: loadingMessageId,
      role: "assistant",
      content: "",
      timestamp: Date.now(),
      isLoading: true,
    };

    currentRequestMessagesRef.current = [userMessage.id, loadingMessageId];

    ma.addMessage(userMessage);
    ma.addMessage(loadingMessage);
    setInput("");
    ma.clearUploadedFiles();
    ma.setIsRunning(true);
    setStreamingMessageId(loadingMessageId);
    setStreamingContent("");
    setStreamingEvents([]);
    setCurrentOutputFiles([]);

    try {
      if (rm === 'non_streaming' && sa.runSync) {
        // ── Non-streaming (sync) mode ──
        const result = await sa.runSync(userMessage.content, agentFiles);

        const events: StreamEventRecord[] = [];
        let eventId = 0;
        const now = Date.now();

        if (result.steps && result.steps.length > 0) {
          for (const step of result.steps) {
            if (step.tool_name) {
              events.push({
                id: `sync-${eventId++}`,
                type: 'tool_call',
                timestamp: now,
                data: { toolName: step.tool_name, toolInput: step.tool_input as Record<string, unknown> | undefined },
              });
              if (step.content) {
                events.push({
                  id: `sync-${eventId++}`,
                  type: 'tool_result',
                  timestamp: now,
                  data: { toolName: step.tool_name, toolResult: step.content, success: true },
                });
              }
            } else if (step.content) {
              events.push({
                id: `sync-${eventId++}`,
                type: 'assistant',
                timestamp: now,
                data: { content: step.content },
              });
            }
          }
        }

        events.push({
          id: `sync-${eventId++}`,
          type: 'complete',
          timestamp: now,
          data: { success: result.success, answer: result.answer, totalTurns: result.total_turns },
        });

        if (result.error) {
          events.push({
            id: `sync-${eventId++}`,
            type: 'error',
            timestamp: now,
            data: { message: result.error },
          });
        }

        ma.updateMessage(loadingMessageId, {
          content: serializeEventsToText(events),
          streamEvents: events,
          rawAnswer: result.answer || undefined,
          isLoading: false,
          traceId: result.trace_id,
          error: result.error,
        });
      } else {
        // ── Streaming mode ──
        const events: StreamEventRecord[] = [];
        let finalAnswer = "";
        let traceId: string | undefined;
        let hasError = false;
        let errorMessage = "";
        let isComplete = false;
        const outputFiles: OutputFileInfo[] = [];

        await sa.runStream(
          userMessage.content,
          agentFiles,
          (event: StreamEvent) => {
            handleStreamEvent(event, events);

            switch (event.event_type) {
              case "run_started":
                traceId = event.trace_id;
                currentTraceIdRef.current = traceId || null;
                if (event.session_id && onSid) {
                  onSid(event.session_id);
                }
                flushSync(() => {
                  ma.updateMessage(loadingMessageId, { traceId: traceId });
                });
                break;
              case "complete":
                if (isComplete) break;
                isComplete = true;
                finalAnswer = event.answer || "";
                // Check success===false (fix for FullscreenChat bug)
                if (event.success === false && !hasError) {
                  hasError = true;
                  errorMessage = event.error || event.answer || "Agent run failed";
                }
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

        ma.updateMessage(loadingMessageId, {
          content: serializeEventsToText(events),
          streamEvents: events,
          rawAnswer: finalAnswer || undefined,
          isLoading: false,
          traceId: traceId,
          error: hasError ? errorMessage : undefined,
          outputFiles: outputFiles.length > 0 ? outputFiles : undefined,
        });
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      ma.updateMessage(loadingMessageId, {
        content: "Failed to run agent",
        isLoading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      ma.setIsRunning(false);
      setStreamingMessageId(null);
      setStreamingContent(null);
      setStreamingEvents([]);
      setCurrentOutputFiles([]);
      abortControllerRef.current = null;
      currentRequestMessagesRef.current = [];
      currentTraceIdRef.current = null;
    }
  }, [input, handleSteer]);

  const handleKeyDown = React.useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const handleStop = React.useCallback(() => {
    const ma = adapterRef.current.messageAdapter;
    if (!ma.getIsRunning() || !abortControllerRef.current) return;

    abortControllerRef.current.abort();

    if (currentRequestMessagesRef.current.length > 0) {
      ma.removeMessages(currentRequestMessagesRef.current);
    }

    ma.setIsRunning(false);
    setStreamingMessageId(null);
    setStreamingContent(null);
    setStreamingEvents([]);
    setCurrentOutputFiles([]);
    abortControllerRef.current = null;
    currentRequestMessagesRef.current = [];
    currentTraceIdRef.current = null;
  }, []);

  const handleFileUpload = React.useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        const uploadedFile = await filesApi.upload(file);
        adapterRef.current.messageAdapter.addUploadedFile(uploadedFile);
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
  }, []);

  const handleRemoveFile = React.useCallback(async (fileId: string) => {
    try {
      await filesApi.delete(fileId);
    } catch {
      // Ignore server delete errors
    }
    adapterRef.current.messageAdapter.removeUploadedFile(fileId);
  }, []);

  return {
    input,
    setInput,
    handleSubmit,
    handleStop,
    handleKeyDown,
    handleFileUpload,
    handleRemoveFile,
    streamingContent,
    streamingEvents,
    streamingMessageId,
    currentOutputFiles,
    isUploading,
    fileInputRef,
    messagesEndRef,
  };
}

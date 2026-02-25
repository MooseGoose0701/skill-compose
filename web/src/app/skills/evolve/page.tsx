"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { flushSync } from "react-dom";
import {
  ArrowLeft,
  ExternalLink,
  Square,
  Zap,
  MessageSquare,
  CheckCircle2,
  Send,
  PanelLeft,
  History,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSkills } from "@/hooks/use-skills";
import { skillsApi, tracesApi, agentPresetsApi, agentApi } from "@/lib/api";
import type {
  TraceListItem,
  StreamEvent,
  OutputFileInfo,
  AgentPreset,
} from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import { ChatMessageItem } from "@/components/chat/chat-message";
import type { StreamEventRecord } from "@/types/stream-events";
import { handleStreamEvent, serializeEventsToText } from "@/lib/stream-utils";
import { useTranslation } from "@/i18n/client";
import { generateUUID } from "@/lib/utils";
import { toast } from "sonner";
import { SessionSidebar } from "@/components/published/session-sidebar";
import { useQueryClient } from "@tanstack/react-query";
import { publishedSessionKeys } from "@/hooks/use-published-sessions";
import { sessionMessagesToChatMessages } from "@/lib/session-utils";

interface LocalMessage extends ChatMessage {}

type Phase = "select" | "chat";

export default function SkillEvolvePage() {
  const { t } = useTranslation("skills");
  const { t: tc } = useTranslation("common");
  const searchParams = useSearchParams();
  const { data, isLoading } = useSkills();
  const queryClient = useQueryClient();

  // Phase state
  const [phase, setPhase] = useState<Phase>("select");

  // Selection state
  const [selectedSkill, setSelectedSkill] = useState<string>("");
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [selectedTraceIds, setSelectedTraceIds] = useState<Set<string>>(
    new Set()
  );
  const [feedback, setFeedback] = useState("");
  const [tracesLoading, setTracesLoading] = useState(false);
  const [showAllTraces, setShowAllTraces] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [streamingEvents, setStreamingEvents] = useState<StreamEventRecord[]>(
    []
  );
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(
    null
  );
  const [currentOutputFiles, setCurrentOutputFiles] = useState<
    OutputFileInfo[]
  >([]);
  const [agentPreset, setAgentPreset] = useState<AgentPreset | null>(null);
  const [agentLoadError, setAgentLoadError] = useState<string | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [evolutionComplete, setEvolutionComplete] = useState(false);
  const [syncResult, setSyncResult] = useState<{
    synced: boolean;
    new_version?: string;
  } | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const initialMessageSentRef = useRef(false);

  // Session ID for server-side session management (new per evolve chat)
  const [sessionId, setEvolveSessionId] = useState(() => generateUUID());

  const hasTraces = selectedTraceIds.size > 0;
  const hasFeedback = feedback.trim().length > 0;
  const canStartChat = (hasTraces || hasFeedback) && selectedSkill;

  const userSkills = useMemo(
    () => (data?.skills ?? []).filter((s) => s.skill_type === "user"),
    [data]
  );

  // Pre-select skill from URL param
  useEffect(() => {
    const skillParam = searchParams.get("skill");
    if (skillParam && !selectedSkill) {
      setSelectedSkill(skillParam);
    }
  }, [searchParams, selectedSkill]);

  // Load traces when skill is selected or showAllTraces changes
  useEffect(() => {
    if (!selectedSkill) return;

    const loadTraces = async () => {
      setTracesLoading(true);
      try {
        const params: { skill_name?: string; limit: number } = { limit: 100 };
        if (!showAllTraces) {
          params.skill_name = selectedSkill;
        }
        const response = await tracesApi.list(params);
        setTraces(response.traces);
        setSelectedTraceIds(new Set());
      } catch (err) {
        console.error("Failed to load traces:", err);
        setTraces([]);
      } finally {
        setTracesLoading(false);
      }
    };

    loadTraces();
  }, [selectedSkill, showAllTraces]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Auto-refresh session list when chat completes
  const prevIsRunning = useRef(isRunning);
  useEffect(() => {
    if (prevIsRunning.current && !isRunning) {
      queryClient.invalidateQueries({ queryKey: publishedSessionKeys.lists() });
    }
    prevIsRunning.current = isRunning;
  }, [isRunning, queryClient]);

  // Auto-send initial message when entering chat phase
  useEffect(() => {
    if (phase === "chat" && agentPreset && !initialMessageSentRef.current) {
      initialMessageSentRef.current = true;
      sendInitialMessage();
    }
  }, [phase, agentPreset]);

  const handleSkillChange = (name: string) => {
    setSelectedSkill(name);
    setTraces([]);
    setSelectedTraceIds(new Set());
    setFeedback("");
    setShowAllTraces(false);
  };

  const toggleTraceSelection = (traceId: string) => {
    const newSelected = new Set(selectedTraceIds);
    if (newSelected.has(traceId)) {
      newSelected.delete(traceId);
    } else {
      newSelected.add(traceId);
    }
    setSelectedTraceIds(newSelected);
  };

  const toggleAllTraces = () => {
    if (selectedTraceIds.size === traces.length) {
      setSelectedTraceIds(new Set());
    } else {
      setSelectedTraceIds(new Set(traces.map((t) => t.id)));
    }
  };

  const addMessage = useCallback((msg: LocalMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateMessage = useCallback(
    (id: string, updates: Partial<LocalMessage>) => {
      setMessages((prev) =>
        prev.map((msg) => (msg.id === id ? { ...msg, ...updates } : msg))
      );
    },
    []
  );

  const handleStartChat = async () => {
    setAgentLoadError(null);
    try {
      const preset = await agentPresetsApi.getByName("skill-evolve-helper");
      setAgentPreset(preset);
      const newSessionId = generateUUID();
      setEvolveSessionId(newSessionId);
      sessionStorage.setItem("evolve-session-id", newSessionId);
      setPhase("chat");
    } catch {
      setAgentLoadError(t("evolve.agentNotFound"));
    }
  };

  const handleBackToSelection = () => {
    if (isRunning) return;
    setPhase("select");
    setMessages([]);
    setEvolutionComplete(false);
    setSyncResult(null);
    initialMessageSentRef.current = false;
  };

  const handleNewChat = useCallback(() => {
    if (isRunning) return;
    setPhase("select");
    setMessages([]);
    setEvolutionComplete(false);
    setSyncResult(null);
    initialMessageSentRef.current = false;
    setMobileSidebarOpen(false);
  }, [isRunning]);

  const handleSessionSwitch = useCallback(async (newSessionId: string) => {
    if (newSessionId === sessionId || isRunning) return;

    setEvolveSessionId(newSessionId);
    setMessages([]);
    setEvolutionComplete(false);
    setSyncResult(null);
    setMobileSidebarOpen(false);
    // Prevent auto-send of initial message when loading an existing session
    initialMessageSentRef.current = true;

    sessionStorage.setItem("evolve-session-id", newSessionId);

    try {
      const data = await agentApi.getSession(newSessionId);
      if (data.messages.length > 0) {
        const restoredMessages = sessionMessagesToChatMessages(data.messages);
        setMessages(restoredMessages);

        // Extract skill name from first user message
        const firstUserMsg = restoredMessages.find(m => m.role === "user");
        if (firstUserMsg?.content) {
          const match = firstUserMsg.content.match(/evolve the skill "([^"]+)"/);
          if (match) {
            setSelectedSkill(match[1]);
          }
        }
      }
    } catch {
      // Session not found or empty
    }
  }, [sessionId, isRunning]);

  const handleViewHistory = async () => {
    setAgentLoadError(null);
    try {
      const preset = agentPreset || await agentPresetsApi.getByName("skill-evolve-helper");
      setAgentPreset(preset);
      // Don't auto-send initial message — just show the sidebar with past sessions
      initialMessageSentRef.current = true;
      setPhase("chat");
    } catch {
      setAgentLoadError(t("evolve.agentNotFound"));
    }
  };

  const buildInitialMessageText = (): string => {
    const parts: string[] = [];
    parts.push(`I want to evolve the skill "${selectedSkill}".`);

    if (hasTraces) {
      const traceIdList = Array.from(selectedTraceIds);
      parts.push(
        `\nPlease analyze these ${traceIdList.length} execution trace(s):`
      );
      for (const id of traceIdList) {
        parts.push(`- Trace ID: ${id}`);
      }
    }

    if (hasFeedback) {
      parts.push(`\nAdditional feedback:\n${feedback.trim()}`);
    }

    if (!hasTraces && hasFeedback) {
      parts.push(
        "\nNo traces were selected. Please analyze based on the feedback and the skill's current content."
      );
    }

    return parts.join("\n");
  };

  const sendMessage = async (
    messageText: string,
    isInitial: boolean = false
  ) => {
    if (!agentPreset) return;

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const userMessage: LocalMessage = {
      id: Date.now().toString(),
      role: "user",
      content: messageText,
      timestamp: Date.now(),
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
    setIsRunning(true);
    setStreamingMessageId(loadingMessageId);
    setStreamingContent("");
    setStreamingEvents([]);
    setCurrentOutputFiles([]);

    try {

      const events: StreamEventRecord[] = [];
      let finalAnswer = "";
      let traceId: string | undefined;
      let hasError = false;
      let errorMessage = "";
      let isComplete = false;
      const outputFiles: OutputFileInfo[] = [];

      await agentApi.runStream(
        {
          request: messageText,
          session_id: sessionId,
          agent_id: agentPreset.id,
        },
        (event: StreamEvent) => {
          handleStreamEvent(event, events);

          switch (event.event_type) {
            case "run_started":
              traceId = event.trace_id;
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
              errorMessage =
                event.message || event.error || "Unknown error";
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
                  content_type:
                    event.content_type || "application/octet-stream",
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

      // After completion, try to sync filesystem to create a new DB version
      if (isComplete && !hasError) {
        try {
          const sync = await skillsApi.syncFilesystem(selectedSkill);
          if (sync.synced) {
            setSyncResult(sync);
            setEvolutionComplete(true);
            toast.success(
              t("evolve.evolutionComplete")
            );
          }
        } catch {
          // Sync failure is non-fatal
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Remove loading message on abort
        setMessages((prev) =>
          prev.filter((m) => m.id !== loadingMessageId)
        );
        return;
      }
      updateMessage(loadingMessageId, {
        content: t("evolve.failedToRunAgent"),
        isLoading: false,
        error: err instanceof Error ? err.message : tc("errors.generic"),
      });
    } finally {
      setIsRunning(false);
      setStreamingMessageId(null);
      setStreamingContent(null);
      setStreamingEvents([]);
      setCurrentOutputFiles([]);
      abortControllerRef.current = null;
    }
  };

  const sendInitialMessage = () => {
    const text = buildInitialMessageText();
    sendMessage(text, true);
  };

  const handleSubmit = () => {
    if (!input.trim() || isRunning) return;
    const text = input.trim();
    setInput("");
    sendMessage(text);
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
    setIsRunning(false);
    setStreamingMessageId(null);
    setStreamingContent(null);
    setStreamingEvents([]);
    setCurrentOutputFiles([]);
    abortControllerRef.current = null;
  };

  // ─── Phase 1: Selection ───────────────────────────────────────────

  if (phase === "select") {
    return (
      <div className="container max-w-3xl py-10 px-4">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div className="flex-1">
            <h1 className="text-2xl font-bold tracking-tight">
              {t("evolve.title")}
            </h1>
            <p className="text-sm text-muted-foreground">
              {t("evolve.description")}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={handleViewHistory}>
            <History className="h-4 w-4 mr-1.5" />
            {t("evolve.history")}
          </Button>
        </div>

        {/* Skill selector */}
        <div className="mb-8">
          <label className="block text-sm font-medium mb-2">
            {t("evolve.selectSkill")}
          </label>
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-2">
              <Spinner size="md" />
              <span>{tc("actions.loading")}</span>
            </div>
          ) : userSkills.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("evolve.noUserSkills")}{" "}
              <Link href="/skills/new" className="text-primary underline">
                {t("evolve.createOneFirst")}
              </Link>
              .
            </p>
          ) : (
            <Select value={selectedSkill} onValueChange={handleSkillChange}>
              <SelectTrigger className="w-64">
                <SelectValue placeholder={t("evolve.chooseSkill")} />
              </SelectTrigger>
              <SelectContent className="max-w-[320px] pr-4">
                {userSkills.map((skill) => (
                  <SelectItem key={skill.name} value={skill.name}>
                    <span className="truncate">
                      {skill.name}
                      {skill.description ? ` — ${skill.description}` : ""}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Traces and feedback */}
        {selectedSkill && (
          <div className="space-y-6">
            {/* Traces section */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium">
                  {t("evolve.selectTraces")}{" "}
                  <span className="text-muted-foreground font-normal">
                    ({t("evolve.optional")})
                  </span>
                </h3>
                <label className="flex items-center gap-1.5 cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors">
                  <input
                    type="checkbox"
                    checked={showAllTraces}
                    onChange={(e) => setShowAllTraces(e.target.checked)}
                    className="h-3.5 w-3.5 rounded border-gray-300"
                  />
                  {t("evolve.showAllTraces")}
                </label>
              </div>
              {tracesLoading ? (
                <div className="flex items-center justify-center py-4">
                  <Spinner size="lg" />
                  <span className="ml-2 text-muted-foreground">
                    {tc("actions.loading")}
                  </span>
                </div>
              ) : traces.length === 0 ? (
                <div className="text-center py-4 border rounded-lg bg-muted/30">
                  <p className="text-sm text-muted-foreground">
                    {t("evolve.noTraces")}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 pb-2 border-b">
                    <input
                      type="checkbox"
                      checked={selectedTraceIds.size === traces.length}
                      onChange={toggleAllTraces}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm font-medium">
                      {tc("actions.selectAll")} ({selectedTraceIds.size}/
                      {traces.length})
                    </span>
                  </div>
                  {traces.map((trace) => (
                    <div
                      key={trace.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                        selectedTraceIds.has(trace.id)
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-muted/50"
                      }`}
                      onClick={() => toggleTraceSelection(trace.id)}
                    >
                      <input
                        type="checkbox"
                        checked={selectedTraceIds.has(trace.id)}
                        onChange={() => toggleTraceSelection(trace.id)}
                        className="h-4 w-4 mt-1 rounded border-gray-300"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={trace.success ? "success" : "error"}
                          >
                            {trace.success ? t("evolve.traceStatus.success") : t("evolve.traceStatus.failed")}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {new Date(trace.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p
                          className="text-sm mt-1 truncate"
                          title={trace.request}
                        >
                          {trace.request}
                        </p>
                        <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                          <span>{t("evolve.traceInfo.turns", { count: trace.total_turns })}</span>
                          <span>
                            {t("evolve.traceInfo.tokens", { count: trace.total_input_tokens + trace.total_output_tokens })}
                          </span>
                          {trace.duration_ms && (
                            <span>
                              {t("evolve.traceInfo.duration", { duration: (trace.duration_ms / 1000).toFixed(1) })}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Feedback section */}
            <div>
              <h3 className="text-sm font-medium mb-2">
                {t("evolve.feedback")}{" "}
                <span className="text-muted-foreground font-normal">
                  ({t("evolve.optional")})
                </span>
              </h3>
              <Textarea
                placeholder={t("evolve.feedbackPlaceholder")}
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={4}
              />
            </div>

            {/* Error */}
            {agentLoadError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md dark:bg-red-950 dark:border-red-800">
                <p className="text-red-600 text-sm dark:text-red-400">
                  {agentLoadError}
                </p>
              </div>
            )}

            {/* Start button */}
            <Button
              onClick={handleStartChat}
              disabled={!canStartChat}
              className="w-full sm:w-auto"
            >
              <MessageSquare className="h-4 w-4 mr-2" />
              {t("evolve.startChat")}
            </Button>
          </div>
        )}
      </div>
    );
  }

  // ─── Phase 2: Chat ────────────────────────────────────────────────

  return (
    <div className="flex h-screen">
      {/* Desktop sidebar */}
      {agentPreset && (
        <div className="w-[260px] shrink-0 hidden md:flex flex-col border-r bg-muted/30">
          <SessionSidebar
            agentId={agentPreset.id}
            activeSessionId={sessionId}
            onSessionSelect={handleSessionSwitch}
            onNewChat={handleNewChat}
            isRunning={isRunning}
          />
        </div>
      )}

      {/* Mobile sidebar overlay */}
      {mobileSidebarOpen && agentPreset && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-[280px] bg-background border-r shadow-xl flex flex-col animate-in slide-in-from-left duration-200">
            <SessionSidebar
              agentId={agentPreset.id}
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
        <div className="border-b px-4 sm:px-6 py-3 flex items-center gap-3 shrink-0">
          {/* Mobile sidebar toggle */}
          <Button
            variant="ghost"
            size="sm"
            className="md:hidden p-1.5"
            onClick={() => setMobileSidebarOpen(true)}
          >
            <PanelLeft className="h-5 w-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleBackToSelection}
            disabled={isRunning}
            title={t("evolve.backToSelection")}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <Zap className="h-5 w-5 text-primary" />
          <div className="flex-1 min-w-0">
            <h1 className="font-semibold text-base truncate">
              {t("evolve.evolving")}: {selectedSkill}
            </h1>
          </div>
          <Link href={`/skills/${encodeURIComponent(selectedSkill)}`} target="_blank">
            <Button variant="outline" size="sm">
              {t("evolve.viewSkill")}
              <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>

        {/* Evolution complete banner */}
        {evolutionComplete && syncResult?.synced && (
          <div className="mx-4 sm:mx-6 mt-3 p-3 bg-green-50 border border-green-200 rounded-md dark:bg-green-950 dark:border-green-800">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
              <p className="text-green-800 text-sm font-medium dark:text-green-200">
                {t("evolve.evolutionComplete")}
                {syncResult.new_version && (
                  <span className="font-normal ml-1">
                    (v{syncResult.new_version})
                  </span>
                )}
              </p>
            </div>
            <div className="mt-2">
              <Link
                href={`/skills/${encodeURIComponent(selectedSkill)}?tab=resources`}
                target="_blank"
              >
                <Button variant="outline" size="sm">
                  {t("evolve.viewSkill")}
                  <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-muted-foreground py-16">
              <Zap className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg">{t("evolve.startConversation")}</p>
            </div>
          ) : (
            messages.map((message, idx) => (
              <div key={message.id} className="max-w-4xl mx-auto">
                <ChatMessageItem
                  message={message}
                  streamingContent={
                    message.id === streamingMessageId
                      ? streamingContent
                      : null
                  }
                  streamingEvents={
                    message.id === streamingMessageId
                      ? streamingEvents
                      : undefined
                  }
                  streamingOutputFiles={
                    message.id === streamingMessageId
                      ? currentOutputFiles
                      : undefined
                  }
                  askUserAnswer={message.role === 'assistant' && messages[idx + 1]?.role === 'user' ? messages[idx + 1].content : undefined}
                />
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t px-4 sm:px-6 py-4 shrink-0">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t("evolve.guidePlaceholder")}
                className="min-h-[60px] resize-none"
                disabled={isRunning}
              />
            </div>
            <div className="flex justify-between items-center mt-2">
              <span className="text-xs text-muted-foreground">
                {t("evolve.enterToSend")}
              </span>
              {isRunning ? (
                <Button onClick={handleStop} variant="destructive" size="sm">
                  <Square className="h-4 w-4 mr-1" />
                  {tc("actions.stop")}
                </Button>
              ) : (
                <Button
                  onClick={handleSubmit}
                  disabled={!input.trim()}
                  size="sm"
                >
                  <Send className="h-4 w-4 mr-1" />
                  {t("evolve.send")}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

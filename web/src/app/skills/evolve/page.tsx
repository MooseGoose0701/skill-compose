"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
  X,
  Search,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSkills } from "@/hooks/use-skills";
import { useAgentPresets } from "@/hooks/use-agents";
import { skillsApi, tracesApi, agentPresetsApi, agentApi } from "@/lib/api";
import type {
  TraceListItem,
  AgentPreset,
} from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import { ChatMessageItem } from "@/components/chat/chat-message";
import { useChatEngine } from "@/hooks/use-chat-engine";
import { useTranslation } from "@/i18n/client";
import { generateUUID } from "@/lib/utils";
import { toast } from "sonner";
import { SessionSidebar } from "@/components/published/session-sidebar";
import { useQueryClient } from "@tanstack/react-query";
import { publishedSessionKeys } from "@/hooks/use-published-sessions";
import { sessionMessagesToChatMessages } from "@/lib/session-utils";

type Phase = "select" | "chat";

const MAX_SKILLS = 5;
const CLEAR_AGENT_VALUE = "__clear__";

export default function SkillEvolvePage() {
  const { t } = useTranslation("skills");
  const { t: tc } = useTranslation("common");
  const searchParams = useSearchParams();
  const { data: skillsData, isLoading: skillsLoading } = useSkills();
  const { data: agentsData, isLoading: agentsLoading } = useAgentPresets({ is_system: false });
  const queryClient = useQueryClient();

  // Phase state
  const [phase, setPhase] = useState<Phase>("select");

  // Selection state — multi-skill + optional agent
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<{ id: string; name: string } | null>(null);
  const [skillSearch, setSkillSearch] = useState("");
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [selectedTraceIds, setSelectedTraceIds] = useState<Set<string>>(
    new Set()
  );
  const [feedback, setFeedback] = useState("");
  const [tracesLoading, setTracesLoading] = useState(false);
  const [showAllTraces, setShowAllTraces] = useState(false);

  // Chat state (local, no Zustand)
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [agentPreset, setAgentPreset] = useState<AgentPreset | null>(null);
  const [agentLoadError, setAgentLoadError] = useState<string | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [evolutionComplete, setEvolutionComplete] = useState(false);
  const [syncResults, setSyncResults] = useState<
    Array<{ name: string; synced: boolean; new_version?: string }>
  >([]);

  // Session ID for server-side session management (new per evolve chat)
  const [sessionId, setEvolveSessionId] = useState(() => generateUUID());

  // Refs
  const initialMessageSentRef = useRef(false);

  // Stable refs for engine callbacks (avoid stale closures)
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const isRunningRef = useRef(isRunning);
  isRunningRef.current = isRunning;
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const selectedSkillsRef = useRef(selectedSkills);
  selectedSkillsRef.current = selectedSkills;
  const selectedAgentRef = useRef(selectedAgent);
  selectedAgentRef.current = selectedAgent;

  const hasTargets = selectedSkills.length > 0 || selectedAgent !== null;
  const hasTraces = selectedTraceIds.size > 0;
  const hasFeedback = feedback.trim().length > 0;
  const hasEvidence = hasTraces || hasFeedback;
  const canStartChat = hasTargets && hasEvidence;

  const userSkills = useMemo(
    () => (skillsData?.skills ?? []).filter((s) => s.skill_type === "user"),
    [skillsData]
  );

  const userAgents = useMemo(
    () => agentsData?.presets ?? [],
    [agentsData]
  );

  const filteredSkills = useMemo(() => {
    if (!skillSearch.trim()) return userSkills;
    const q = skillSearch.toLowerCase();
    return userSkills.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.description && s.description.toLowerCase().includes(q))
    );
  }, [userSkills, skillSearch]);

  // Stable callbacks for messageAdapter
  const addMessage = useCallback((msg: ChatMessage) => {
    setMessages(prev => [...prev, msg]);
  }, []);

  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(m => (m.id === id ? { ...m, ...updates } : m)));
  }, []);

  const removeMessages = useCallback((ids: string[]) => {
    setMessages(prev => prev.filter(m => !ids.includes(m.id)));
  }, []);

  // Stable ref for agentPreset (used inside engine callbacks)
  const agentPresetRef = useRef(agentPreset);
  agentPresetRef.current = agentPreset;

  // Chat engine (following skill-finder-chat pattern)
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
      runStream: async (request, _agentFiles, onEvent, signal) => {
        await agentApi.runStream(
          {
            request,
            session_id: sessionIdRef.current,
            agent_id: agentPresetRef.current!.id,
          },
          onEvent,
          signal
        );
      },
      steer: async (traceId, message) => {
        await agentApi.steerAgent(traceId, message);
      },
    },
    validateBeforeRun: () => {
      if (!agentPresetRef.current) {
        return t("evolve.agentNotFound");
      }
      return null;
    },
  });

  // Pre-select skill from URL param
  useEffect(() => {
    const skillParam = searchParams.get("skill");
    if (skillParam && selectedSkills.length === 0) {
      setSelectedSkills([skillParam]);
    }
  }, [searchParams, selectedSkills.length]);

  // Load traces when skills change or showAllTraces changes
  useEffect(() => {
    if (!hasTargets) return;

    const loadTraces = async () => {
      setTracesLoading(true);
      try {
        if (!showAllTraces && selectedSkills.length > 0) {
          // Fetch traces for each selected skill and dedup by ID
          const allTraces = await Promise.all(
            selectedSkills.map((name) => tracesApi.list({ skill_name: name, limit: 100 }))
          );
          const seen = new Set<string>();
          const deduped: TraceListItem[] = [];
          for (const resp of allTraces) {
            for (const trace of resp.traces) {
              if (!seen.has(trace.id)) {
                seen.add(trace.id);
                deduped.push(trace);
              }
            }
          }
          // Sort newest first
          deduped.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          setTraces(deduped);
        } else {
          const response = await tracesApi.list({ limit: 100 });
          setTraces(response.traces);
        }
        setSelectedTraceIds(new Set());
      } catch (err) {
        console.error("Failed to load traces:", err);
        setTraces([]);
      } finally {
        setTracesLoading(false);
      }
    };

    loadTraces();
  }, [selectedSkills, showAllTraces, hasTargets]); // eslint-disable-line react-hooks/exhaustive-deps -- selectedAgent intentionally omitted: not used for trace filtering

  // Auto-scroll
  useEffect(() => {
    engine.messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, engine.streamingContent]);

  // Post-completion: refresh session list + filesystem sync
  const prevIsRunning = useRef(isRunning);
  useEffect(() => {
    if (prevIsRunning.current && !isRunning) {
      queryClient.invalidateQueries({ queryKey: publishedSessionKeys.lists() });
      handlePostCompletionSync();
    }
    prevIsRunning.current = isRunning;
  }, [isRunning, queryClient]); // eslint-disable-line react-hooks/exhaustive-deps -- handlePostCompletionSync reads values via refs, no stale closure risk

  const handlePostCompletionSync = async () => {
    // Check if last assistant message has an error
    const lastMsg = messagesRef.current[messagesRef.current.length - 1];
    if (lastMsg?.error) return;

    const skills = selectedSkillsRef.current;
    const agent = selectedAgentRef.current;

    const results: Array<{ name: string; synced: boolean; new_version?: string }> = [];
    for (const skillName of skills) {
      try {
        const sync = await skillsApi.syncFilesystem(skillName);
        results.push({ name: skillName, synced: sync.synced, new_version: sync.new_version });
      } catch {
        results.push({ name: skillName, synced: false });
      }
    }
    const syncedNames = results.filter((r) => r.synced).map((r) => r.name);
    // Show banner whenever the run completed without error (provides links to targets)
    setSyncResults(results);
    setEvolutionComplete(true);
    // Single summary toast instead of per-skill + overall
    if (syncedNames.length > 0) {
      toast.success(t("evolve.skillsSyncedSummary", { names: syncedNames.join(", "), count: syncedNames.length }));
    } else {
      toast.success(t("evolve.evolutionComplete"));
    }
  };

  // Auto-send initial message when entering chat phase
  useEffect(() => {
    if (phase === "chat" && agentPreset && !initialMessageSentRef.current) {
      initialMessageSentRef.current = true;
      engine.handleSubmit(buildInitialMessageText());
    }
  }, [phase, agentPreset]); // eslint-disable-line react-hooks/exhaustive-deps -- intentionally omit engine/buildInitialMessageText; only trigger on phase/agentPreset change

  const toggleSkillSelection = (name: string) => {
    setSelectedSkills((prev) => {
      if (prev.includes(name)) {
        return prev.filter((s) => s !== name);
      }
      if (prev.length >= MAX_SKILLS) return prev;
      return [...prev, name];
    });
  };

  const removeSkill = (name: string) => {
    setSelectedSkills((prev) => prev.filter((s) => s !== name));
  };

  const handleAgentChange = (value: string) => {
    if (value === CLEAR_AGENT_VALUE) {
      setSelectedAgent(null);
      return;
    }
    const agent = userAgents.find((a) => a.id === value);
    if (agent) {
      setSelectedAgent({ id: agent.id, name: agent.name });
    }
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

  const handleStartChat = async () => {
    setAgentLoadError(null);
    try {
      const preset = await agentPresetsApi.getByName("agent-skill-evolver");
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
    setSyncResults([]);
    initialMessageSentRef.current = false;
  };

  const handleNewChat = useCallback(() => {
    if (isRunning) return;
    setPhase("select");
    setMessages([]);
    setEvolutionComplete(false);
    setSyncResults([]);
    initialMessageSentRef.current = false;
    setMobileSidebarOpen(false);
  }, [isRunning]);

  const handleSessionSwitch = useCallback(async (newSessionId: string) => {
    if (newSessionId === sessionId || isRunning) return;

    setEvolveSessionId(newSessionId);
    setMessages([]);
    setEvolutionComplete(false);
    setSyncResults([]);
    setMobileSidebarOpen(false);
    // Prevent auto-send of initial message when loading an existing session
    initialMessageSentRef.current = true;

    sessionStorage.setItem("evolve-session-id", newSessionId);

    try {
      const data = await agentApi.getSession(newSessionId);
      if (data.messages.length > 0) {
        const restoredMessages = sessionMessagesToChatMessages(data.messages);
        setMessages(restoredMessages);

        // Extract skill names from the structured initial message
        const firstUserMsg = restoredMessages.find(m => m.role === "user");
        if (firstUserMsg?.content) {
          // Only parse lines between "## Target Skills" and the next "##" heading
          const skillSection = firstUserMsg.content.match(/## Target Skills\n([\s\S]*?)(?=\n##|$)/);
          if (skillSection) {
            const skills = skillSection[1]
              .split('\n')
              .filter(line => line.startsWith('- '))
              .map(line => line.replace(/^- /, '').trim())
              .filter(Boolean);
            if (skills.length > 0) {
              setSelectedSkills(skills);
            }
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
      const preset = agentPreset || await agentPresetsApi.getByName("agent-skill-evolver");
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
    parts.push("I want to evolve the following:");

    if (selectedSkills.length > 0) {
      parts.push("\n## Target Skills");
      for (const name of selectedSkills) {
        parts.push(`- ${name}`);
      }
    }

    if (selectedAgent) {
      parts.push("\n## Target Agent");
      parts.push(`- Agent: "${selectedAgent.name}" (ID: ${selectedAgent.id})`);
    }

    if (hasTraces) {
      const traceIdList = Array.from(selectedTraceIds);
      parts.push("\n## Execution Traces");
      for (const id of traceIdList) {
        parts.push(`- Trace ID: ${id}`);
      }
    }

    if (hasFeedback) {
      parts.push(`\n## Additional Feedback\n${feedback.trim()}`);
    }

    if (!hasTraces && hasFeedback) {
      parts.push(
        "\nNo traces were selected. Please analyze based on the feedback and the current content."
      );
    }

    return parts.join("\n");
  };

  // Build chat header label
  const chatHeaderLabel = useMemo(() => {
    const parts: string[] = [];
    if (selectedSkills.length > 0) {
      parts.push(selectedSkills.join(", "));
    }
    if (selectedAgent) {
      parts.push(selectedAgent.name);
    }
    return parts.join(" + ");
  }, [selectedSkills, selectedAgent]);

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

        {/* ── Targets Section ── */}
        <div className="mb-8 border rounded-lg p-5">
          <h2 className="text-sm font-semibold mb-4">{t("evolve.targets")}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Skills multi-select */}
            <div>
              <label className="block text-sm font-medium mb-2">
                {t("evolve.selectSkills")}
              </label>
              {skillsLoading ? (
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
                <div>
                  {/* Search input */}
                  <div className="relative mb-2">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t("evolve.searchSkills")}
                      value={skillSearch}
                      onChange={(e) => setSkillSearch(e.target.value)}
                      className="pl-9 h-9"
                    />
                  </div>
                  {/* Skill list with checkboxes */}
                  <div className="border rounded-md max-h-[200px] overflow-auto">
                    {filteredSkills.length === 0 ? (
                      <p className="text-sm text-muted-foreground p-3 text-center">
                        {t("evolve.noUserSkills")}
                      </p>
                    ) : (
                      filteredSkills.map((skill) => {
                        const isSelected = selectedSkills.includes(skill.name);
                        const isDisabled = !isSelected && selectedSkills.length >= MAX_SKILLS;
                        return (
                          <label
                            key={skill.name}
                            className={`flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-muted/50 transition-colors border-b last:border-b-0 ${
                              isSelected ? "bg-primary/5" : ""
                            } ${isDisabled ? "opacity-50 cursor-not-allowed" : ""}`}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => !isDisabled && toggleSkillSelection(skill.name)}
                              disabled={isDisabled}
                              className="h-4 w-4 rounded border-gray-300"
                            />
                            <span className="text-sm truncate flex-1" title={skill.name}>
                              {skill.name}
                            </span>
                          </label>
                        );
                      })
                    )}
                  </div>
                  {selectedSkills.length >= MAX_SKILLS && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-1.5">
                      {t("evolve.maxSkillsReached")}
                    </p>
                  )}
                </div>
              )}
              {/* Selected skill badges */}
              {selectedSkills.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {selectedSkills.map((name) => (
                    <Badge
                      key={name}
                      variant="secondary"
                      className="gap-1 pr-1"
                    >
                      {name}
                      <button
                        onClick={() => removeSkill(name)}
                        className="ml-0.5 rounded-full hover:bg-muted p-0.5"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {/* Agent single-select */}
            <div>
              <label className="block text-sm font-medium mb-2">
                {t("evolve.selectAgent")}
              </label>
              {agentsLoading ? (
                <div className="flex items-center gap-2 text-muted-foreground py-2">
                  <Spinner size="md" />
                  <span>{tc("actions.loading")}</span>
                </div>
              ) : userAgents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t("evolve.noUserAgents")}
                </p>
              ) : (
                <Select
                  value={selectedAgent?.id ?? ""}
                  onValueChange={handleAgentChange}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("evolve.chooseAgent")} />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedAgent && (
                      <SelectItem value={CLEAR_AGENT_VALUE}>
                        <span className="text-muted-foreground italic">
                          {t("evolve.clearAgent")}
                        </span>
                      </SelectItem>
                    )}
                    {userAgents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {selectedAgent && (
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="secondary" className="gap-1 pr-1">
                    {selectedAgent.name}
                    <button
                      onClick={() => setSelectedAgent(null)}
                      className="ml-0.5 rounded-full hover:bg-muted p-0.5"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                </div>
              )}
            </div>
          </div>
          {!hasTargets && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-3">
              {t("evolve.targetsHint")}
            </p>
          )}
        </div>

        {/* ── Feedback Sources Section ── */}
        {hasTargets && (
          <div className="border rounded-lg p-5 mb-8">
            <h2 className="text-sm font-semibold mb-4">{t("evolve.feedbackSources")}</h2>

            {/* Traces section */}
            <div className="mb-6">
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

            {!hasEvidence && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-3">
                {t("evolve.feedbackSourcesHint")}
              </p>
            )}
          </div>
        )}

        {/* Error */}
        {agentLoadError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md dark:bg-red-950 dark:border-red-800 mb-4">
            <p className="text-red-600 text-sm dark:text-red-400">
              {agentLoadError}
            </p>
          </div>
        )}

        {/* Start button */}
        {hasTargets && (
          <Button
            onClick={handleStartChat}
            disabled={!canStartChat}
            className="w-full sm:w-auto"
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            {t("evolve.startChat")}
          </Button>
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
              {t("evolve.evolving")}: {chatHeaderLabel}
            </h1>
          </div>
          <div className="flex gap-2">
            {selectedSkills.length > 0 && (
              <Link href={`/skills/${encodeURIComponent(selectedSkills[0])}`} target="_blank">
                <Button variant="outline" size="sm">
                  {t("evolve.viewSkill")}
                  <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </Link>
            )}
            {selectedAgent && (
              <Link href={`/agents/${encodeURIComponent(selectedAgent.id)}`} target="_blank">
                <Button variant="outline" size="sm">
                  {t("evolve.viewAgent")}
                  <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </Link>
            )}
          </div>
        </div>

        {/* Evolution complete banner */}
        {evolutionComplete && (
          <div className="mx-4 sm:mx-6 mt-3 p-3 bg-green-50 border border-green-200 rounded-md dark:bg-green-950 dark:border-green-800">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0" />
              <p className="text-green-800 text-sm font-medium dark:text-green-200">
                {t("evolve.evolutionComplete")}
              </p>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {syncResults
                .filter((r) => r.synced)
                .map((r) => (
                  <Link
                    key={r.name}
                    href={`/skills/${encodeURIComponent(r.name)}?tab=resources`}
                    target="_blank"
                  >
                    <Button variant="outline" size="sm">
                      {r.name} {r.new_version ? `(v${r.new_version})` : ""}
                      <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                    </Button>
                  </Link>
                ))}
              {selectedAgent && (
                <Link
                  href={`/agents/${encodeURIComponent(selectedAgent.id)}`}
                  target="_blank"
                >
                  <Button variant="outline" size="sm">
                    {selectedAgent.name}
                    <ExternalLink className="ml-1.5 h-3.5 w-3.5" />
                  </Button>
                </Link>
              )}
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
                    engine.streamingMessageId === message.id
                      ? engine.streamingContent
                      : undefined
                  }
                  streamingEvents={
                    engine.streamingMessageId === message.id
                      ? engine.streamingEvents
                      : undefined
                  }
                  streamingOutputFiles={
                    engine.streamingMessageId === message.id
                      ? engine.currentOutputFiles
                      : undefined
                  }
                  onAskUserRespond={engine.handleRespond}
                  askUserAnswer={message.role === 'assistant' && messages[idx + 1]?.role === 'user' ? messages[idx + 1].content : undefined}
                />
              </div>
            ))
          )}
          <div ref={engine.messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t px-4 sm:px-6 py-4 shrink-0">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-2">
              <Textarea
                value={engine.input}
                onChange={(e) => engine.setInput(e.target.value)}
                onKeyDown={engine.handleKeyDown}
                placeholder={t("evolve.guidePlaceholder")}
                className="min-h-[60px] resize-none"
              />
            </div>
            <div className="flex justify-between items-center mt-2">
              <span className="text-xs text-muted-foreground">
                {t("evolve.enterToSend")}
              </span>
              {isRunning ? (
                <div className="flex items-center gap-2">
                  <Button onClick={engine.handleStop} variant="destructive" size="sm">
                    <Square className="h-4 w-4 mr-1" />
                    {tc("actions.stop")}
                  </Button>
                  <Button
                    onClick={() => engine.handleSubmit()}
                    disabled={!engine.input.trim()}
                    size="sm"
                  >
                    <Send className="h-4 w-4 mr-1" />
                    {t("evolve.send")}
                  </Button>
                </div>
              ) : (
                <Button
                  onClick={() => engine.handleSubmit()}
                  disabled={!engine.input.trim()}
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

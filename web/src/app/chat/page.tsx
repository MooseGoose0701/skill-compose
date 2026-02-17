"use client";

import React from "react";
import { flushSync } from "react-dom";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  RotateCcw,
  Paperclip,
  X,
  Wrench,
  Plug,
  ChevronDown,
  ChevronUp,
  Square,
  Bot,
  Cpu,
  Server,
  MessageSquare,
  Home,
  Settings,
  Navigation,
  Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { MultiSelect } from "@/components/ui/multi-select";
import { skillsApi, agentApi, filesApi, mcpApi, toolsApi, agentPresetsApi, modelsApi, executorsApi } from "@/lib/api";
import type { StreamEvent, OutputFileInfo } from "@/lib/api";
import { useChatStore, REQUIRED_TOOLS, type ChatMessage } from "@/stores/chat-store";
import { useChatSessionRestore } from "@/hooks/use-chat-session";
import { ChatMessageItem } from "@/components/chat/chat-message";
import type { StreamEventRecord } from "@/types/stream-events";
import { handleStreamEvent, serializeEventsToText } from "@/lib/stream-utils";
import { toast } from "sonner";

export default function FullscreenChatPage() {
  const [input, setInput] = React.useState("");
  const [streamingContent, setStreamingContent] = React.useState<string | null>(null);
  const [streamingEvents, setStreamingEvents] = React.useState<StreamEventRecord[]>([]);
  const [streamingMessageId, setStreamingMessageId] = React.useState<string | null>(null);
  const [currentOutputFiles, setCurrentOutputFiles] = React.useState<OutputFileInfo[]>([]);
  const [showConfig, setShowConfig] = React.useState(false);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  // Use zustand store for persistence (shared with chat panel via localStorage)
  const {
    messages,
    sessionId,
    selectedSkills,
    selectedTools,
    selectedMcpServers,
    isRunning,
    maxTurns,
    uploadedFiles,
    selectedAgentPreset,
    systemPrompt,
    addMessage,
    updateMessage,
    removeMessages,
    clearMessages,
    newSession,
    resetAll,
    setSessionId,
    setSelectedSkills,
    setSelectedTools,
    setSelectedMcpServers,
    setIsRunning,
    setMaxTurns,
    addUploadedFile,
    removeUploadedFile,
    clearUploadedFiles,
    setSelectedAgentPreset,
    setSystemPrompt,
    selectedModelProvider,
    selectedModelName,
    setSelectedModel,
    selectedExecutorId,
    setSelectedExecutorId,
  } = useChatStore();

  // Restore session messages from server on mount
  useChatSessionRestore();

  const [showToolsPanel, setShowToolsPanel] = React.useState(false);
  const [showResetDialog, setShowResetDialog] = React.useState(false);

  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = React.useState(false);

  // For stop functionality
  const abortControllerRef = React.useRef<AbortController | null>(null);
  const currentRequestMessagesRef = React.useRef<string[]>([]);
  const currentTraceIdRef = React.useRef<string | null>(null);

  // Fetch available skills from registry database
  const { data: skillsData } = useQuery({
    queryKey: ["registry-skills-list"],
    queryFn: () => skillsApi.list(),
  });

  // Filter to user skills only (exclude meta skills)
  const skills = (skillsData?.skills || []).filter(s => s.skill_type === 'user');

  // Fetch available tools
  const { data: toolsData } = useQuery({
    queryKey: ["tools-list"],
    queryFn: () => toolsApi.list(),
  });

  const tools = toolsData?.tools || [];

  // Fetch available MCP servers
  const { data: mcpData } = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => mcpApi.listServers(),
  });

  const mcpServers = mcpData?.servers || [];

  // Fetch available agents (only user-created, not system)
  const { data: agentPresetsData, isLoading: isLoadingAgents } = useQuery({
    queryKey: ["agent-presets-user"],
    queryFn: () => agentPresetsApi.list({ is_system: false }),
  });

  const agentPresets = agentPresetsData?.presets || [];

  // Fetch available models grouped by provider
  const { data: modelsData, isLoading: isLoadingModels } = useQuery({
    queryKey: ["models-providers"],
    queryFn: () => modelsApi.listProviders(),
  });

  const modelProviders = modelsData?.providers || [];

  // Fetch executors
  const { data: executorsData } = useQuery({
    queryKey: ["executors-list"],
    queryFn: () => executorsApi.list(),
  });

  const onlineExecutors = (executorsData?.executors || []).filter(e => e.status === 'online');

  // Auto-scroll to bottom
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Initialize selected tools with all tools selected by default
  React.useEffect(() => {
    if (tools.length > 0) {
      if (selectedTools === null) {
        const allToolNames = tools.map((tool) => tool.name);
        setSelectedTools(allToolNames);
      }
    }
  }, [tools, selectedTools, setSelectedTools]);

  // Initialize selected MCP servers - default_enabled servers are auto-selected
  React.useEffect(() => {
    if (mcpServers.length > 0 && selectedMcpServers === null) {
      const defaultEnabledServers = mcpServers
        .filter((server) => server.default_enabled)
        .map((server) => server.name);
      setSelectedMcpServers(defaultEnabledServers);
    }
  }, [mcpServers, selectedMcpServers, setSelectedMcpServers]);

  // Sync systemPrompt from selected preset on page load
  React.useEffect(() => {
    if (agentPresets.length > 0 && selectedAgentPreset) {
      const preset = agentPresets.find((p) => p.id === selectedAgentPreset);
      if (preset && preset.system_prompt && !systemPrompt) {
        setSystemPrompt(preset.system_prompt);
      }
    }
  }, [agentPresets, selectedAgentPreset, systemPrompt, setSystemPrompt]);

  const handleSteer = async (message: string) => {
    const traceId = currentTraceIdRef.current;
    if (!traceId) return;
    try {
      await agentApi.steerAgent(traceId, message);
      setInput("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send steering message");
    }
  };

  const handleSubmit = async () => {
    if (!input.trim()) return;

    // Steering mode
    if (useChatStore.getState().isRunning && currentTraceIdRef.current) {
      await handleSteer(input.trim());
      return;
    }

    if (useChatStore.getState().isRunning) return;

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

    addMessage(userMessage);
    addMessage(loadingMessage);
    setInput("");
    clearUploadedFiles();
    setIsRunning(true);
    setStreamingMessageId(loadingMessageId);
    setStreamingContent("");
    setStreamingEvents([]);
    setCurrentOutputFiles([]);

    try {
      const currentSkills = useChatStore.getState().selectedSkills;
      const skillsList = currentSkills.length > 0 ? currentSkills : undefined;

      // Generate session_id if none exists (deferred creation)
      let currentSessionId = useChatStore.getState().sessionId;
      if (!currentSessionId) {
        currentSessionId = crypto.randomUUID();
        setSessionId(currentSessionId);
      }

      const events: StreamEventRecord[] = [];
      let finalAnswer = "";
      let traceId: string | undefined;
      let hasError = false;
      let errorMessage = "";
      let isComplete = false;
      const outputFiles: OutputFileInfo[] = [];

      const currentState = useChatStore.getState();
      const currentMcpServers = currentState.selectedMcpServers;
      const currentTools = currentState.selectedTools;
      const currentSystemPrompt = currentState.systemPrompt;
      const currentAgentPreset = currentState.selectedAgentPreset;
      const currentModelProvider = currentState.selectedModelProvider;
      const currentModelName = currentState.selectedModelName;
      const currentExecutorId = currentState.selectedExecutorId;

      let agentRequest: import("@/lib/api").AgentRequest;

      if (currentAgentPreset) {
        agentRequest = {
          request: userMessage.content,
          session_id: currentSessionId,
          agent_id: currentAgentPreset,
          uploaded_files: agentFiles,
          model_provider: currentModelProvider || undefined,
          model_name: currentModelName || undefined,
        };
      } else {
        const mcpServersList = (currentMcpServers === null || currentMcpServers.length === 0)
          ? undefined
          : currentMcpServers;

        const toolsList = currentTools && currentTools.length > 0 ? currentTools : undefined;

        agentRequest = {
          request: userMessage.content,
          session_id: currentSessionId,
          skills: skillsList,
          allowed_tools: toolsList,
          max_turns: maxTurns,
          uploaded_files: agentFiles,
          equipped_mcp_servers: mcpServersList,
          system_prompt: currentSystemPrompt || undefined,
          model_provider: currentModelProvider || undefined,
          model_name: currentModelName || undefined,
          executor_id: currentExecutorId || undefined,
        };
      }

      await agentApi.runStream(
        agentRequest,
        (event: StreamEvent) => {
          // Accumulate text_delta into assistant records, or map other events
          handleStreamEvent(event, events);

          // Handle special cases
          switch (event.event_type) {
            case "run_started":
              traceId = event.trace_id;
              currentTraceIdRef.current = traceId || null;
              if (event.session_id) {
                setSessionId(event.session_id);
              }
              flushSync(() => {
                updateMessage(loadingMessageId, { traceId: traceId });
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
        traceId: traceId,
        error: hasError ? errorMessage : undefined,
        outputFiles: outputFiles.length > 0 ? outputFiles : undefined,
      });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
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
      currentRequestMessagesRef.current = [];
      currentTraceIdRef.current = null;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleReset = () => {
    if (!isRunning) {
      setShowResetDialog(true);
    }
  };

  const handleStop = async () => {
    if (!isRunning || !abortControllerRef.current) return;

    abortControllerRef.current.abort();

    if (currentRequestMessagesRef.current.length > 0) {
      removeMessages(currentRequestMessagesRef.current);
    }

    setIsRunning(false);
    setStreamingMessageId(null);
    setStreamingContent(null);
    setStreamingEvents([]);
    setCurrentOutputFiles([]);
    abortControllerRef.current = null;
    currentRequestMessagesRef.current = [];
    currentTraceIdRef.current = null;
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    try {
      for (const file of Array.from(files)) {
        const uploadedFile = await filesApi.upload(file);
        addUploadedFile(uploadedFile);
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
      removeUploadedFile(fileId);
    } catch (err) {
      console.error("Failed to delete file:", err);
      removeUploadedFile(fileId);
    }
  };

  // Get current agent name for display
  const currentAgentName = selectedAgentPreset
    ? agentPresets.find((p) => p.id === selectedAgentPreset)?.name || "Custom"
    : "Custom Config";

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b px-6 py-4 flex items-center gap-3 shrink-0">
        <MessageSquare className="h-6 w-6 text-primary" />
        <div className="flex-1">
          <h1 className="font-semibold text-lg">Chat</h1>
          <p className="text-sm text-muted-foreground">
            {currentAgentName}
            {selectedModelName && ` • ${selectedModelName}`}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowConfig(!showConfig)}
          title="Toggle configuration"
        >
          <Settings className="h-4 w-4 mr-1" />
          Config
          {showConfig ? <ChevronUp className="h-4 w-4 ml-1" /> : <ChevronDown className="h-4 w-4 ml-1" />}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => newSession()}
          disabled={messages.length === 0 || isRunning}
          title="New Chat"
        >
          <Plus className="h-4 w-4 mr-1" />
          New Chat
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleReset}
          disabled={isRunning}
          title="Reset everything"
        >
          <RotateCcw className="h-4 w-4 mr-1" />
          Reset All
        </Button>
        <Link href="/">
          <Button variant="outline" size="sm" title="Back to home">
            <Home className="h-4 w-4 mr-1" />
            Home
          </Button>
        </Link>
      </div>

      {/* Configuration Panel (collapsible) */}
      {showConfig && (
        <div className="border-b bg-muted/30 px-6 py-4 space-y-4 shrink-0">
          {/* Agent and Model Selectors */}
          <div className="flex flex-wrap items-center gap-4">
            {/* Agent Selector */}
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Agent:</span>
              <select
                value={selectedAgentPreset || ""}
                onChange={(e) => {
                  const presetId = e.target.value;
                  if (!presetId) {
                    setSelectedAgentPreset(null);
                    setSystemPrompt(null);
                  } else {
                    const preset = agentPresets.find((p) => p.id === presetId);
                    if (preset) {
                      setSelectedAgentPreset(preset.id);
                      setSelectedSkills(preset.skill_ids || []);
                      setMaxTurns(preset.max_turns);
                      setSystemPrompt(preset.system_prompt || null);
                      if (preset.builtin_tools === null && tools.length > 0) {
                        setSelectedTools(tools.map(t => t.name));
                      } else if (preset.builtin_tools && preset.builtin_tools.length > 0) {
                        setSelectedTools(preset.builtin_tools);
                      } else {
                        setSelectedTools([]);
                      }
                      setSelectedMcpServers(preset.mcp_servers || []);
                      setSelectedModel(preset.model_provider || null, preset.model_name || null);
                      // Apply executor from preset
                      setSelectedExecutorId(preset.executor_id || null);
                    }
                  }
                }}
                className="h-8 text-sm px-2 rounded border bg-background"
                disabled={isLoadingAgents}
              >
                {isLoadingAgents ? (
                  <option value="">Loading...</option>
                ) : (
                  <>
                    <option value="">Custom Config</option>
                    {agentPresets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.name}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </div>

            {/* Model Selector */}
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Model:</span>
              <select
                value={selectedModelProvider && selectedModelName ? `${selectedModelProvider}/${selectedModelName}` : ""}
                onChange={(e) => {
                  const value = e.target.value;
                  if (!value) {
                    setSelectedModel(null, null);
                  } else {
                    const [provider, ...modelParts] = value.split('/');
                    const modelName = modelParts.join('/');
                    setSelectedModel(provider, modelName);
                  }
                  setSelectedAgentPreset(null);
                }}
                className="h-8 text-sm px-2 rounded border bg-background"
                disabled={isLoadingModels}
              >
                {isLoadingModels ? (
                  <option value="">Loading...</option>
                ) : (
                  <>
                    <option value="">Default</option>
                    {modelProviders.map((provider) => (
                      <optgroup key={provider.name} label={provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}>
                        {provider.models.map((model) => (
                          <option key={model.key} value={model.key}>
                            {model.display_name}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </>
                )}
              </select>
            </div>

            {/* Executor Selector - only show if there are online executors */}
            {onlineExecutors.length > 0 && (
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">Executor:</span>
                <select
                  value={selectedExecutorId || ""}
                  onChange={(e) => {
                    setSelectedExecutorId(e.target.value || null);
                    setSelectedAgentPreset(null);
                  }}
                  className="h-8 text-sm px-2 rounded border bg-background"
                >
                  <option value="">Local</option>
                  {onlineExecutors.map((executor) => (
                    <option key={executor.id} value={executor.id}>
                      {executor.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Skills and Turns */}
          <div className={`flex flex-wrap items-center gap-4 ${selectedAgentPreset ? 'opacity-50' : ''}`}>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Turns:</span>
              <Input
                type="number"
                min={1}
                max={60000}
                value={maxTurns}
                onChange={(e) => {
                  setMaxTurns(parseInt(e.target.value) || 60);
                  setSelectedAgentPreset(null);
                }}
                className="w-16 h-8 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Skills:</span>
              <MultiSelect
                options={skills.map((skill) => ({
                  value: skill.name,
                  label: skill.name,
                  description: skill.description?.slice(0, 50),
                }))}
                selected={selectedSkills}
                onChange={(skills) => {
                  setSelectedSkills(skills);
                  setSelectedAgentPreset(null);
                }}
                placeholder="Select..."
                emptyText="None"
                className="min-w-[150px]"
                size="sm"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowToolsPanel(!showToolsPanel)}
              className="gap-1"
            >
              <Wrench className="h-4 w-4" />
              Tools ({(selectedTools || []).length}/{tools.length})
              {mcpServers.length > 0 && (
                <span className="text-muted-foreground">
                  + MCP ({(selectedMcpServers || []).length})
                </span>
              )}
              {showToolsPanel ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>

          {/* Tools/MCP Panel */}
          {showToolsPanel && (
            <div className={`pt-3 border-t ${selectedAgentPreset ? 'opacity-50' : ''}`}>
              {/* Built-in Tools */}
              <div className="mb-3">
                <div className="flex items-center gap-2 mb-2">
                  <Wrench className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Built-in Tools</span>
                  <span className="text-sm text-muted-foreground">
                    ({(selectedTools || []).length}/{tools.length} selected)
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {tools.map((tool) => {
                    const isRequired = REQUIRED_TOOLS.includes(tool.name);
                    const isSelected = (selectedTools || []).includes(tool.name);
                    return (
                      <button
                        key={tool.id}
                        onClick={() => {
                          if (isRequired) return;
                          const currentTools = selectedTools || [];
                          if (isSelected) {
                            setSelectedTools(currentTools.filter((t) => t !== tool.name));
                          } else {
                            setSelectedTools([...currentTools, tool.name]);
                          }
                          setSelectedAgentPreset(null);
                        }}
                        disabled={isRequired}
                        className={`px-2 py-1 text-sm rounded-md border transition-colors ${
                          isRequired
                            ? 'bg-primary/20 border-primary/50 text-primary cursor-not-allowed'
                            : isSelected
                              ? 'bg-primary/10 border-primary text-primary hover:bg-primary/20'
                              : 'bg-background border-border text-muted-foreground hover:bg-muted'
                        }`}
                        title={isRequired ? `${tool.name} (required)` : tool.description}
                      >
                        {tool.name}
                        {isRequired && <span className="ml-1 text-xs">*</span>}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* MCP Servers */}
              {mcpServers.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Plug className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">MCP Servers</span>
                    <span className="text-sm text-muted-foreground">
                      ({(selectedMcpServers || []).length}/{mcpServers.length} selected)
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {mcpServers.map((server) => {
                      const isSelected = (selectedMcpServers || []).includes(server.name);
                      return (
                        <button
                          key={server.name}
                          onClick={() => {
                            const currentServers = selectedMcpServers || [];
                            if (isSelected) {
                              setSelectedMcpServers(currentServers.filter((s) => s !== server.name));
                            } else {
                              setSelectedMcpServers([...currentServers, server.name]);
                            }
                            setSelectedAgentPreset(null);
                          }}
                          className={`px-2 py-1 text-sm rounded-md border transition-colors ${
                            isSelected
                              ? 'bg-purple-500/10 border-purple-500 text-purple-600 hover:bg-purple-500/20'
                              : 'bg-background border-border text-muted-foreground hover:bg-muted'
                          }`}
                          title={server.description}
                        >
                          {server.display_name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-auto p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-16">
            <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg">Start a conversation</p>
            <p className="text-sm mt-2">Type a message below to begin chatting with the agent.</p>
            {!showConfig && (
              <p className="text-sm mt-1">
                Click <strong>Config</strong> above to customize settings.
              </p>
            )}
          </div>
        ) : (
          messages.map((message) => (
            <div key={message.id} className="max-w-4xl mx-auto">
              <ChatMessageItem
                message={message}
                streamingContent={message.id === streamingMessageId ? streamingContent : null}
                streamingEvents={message.id === streamingMessageId ? streamingEvents : undefined}
                streamingOutputFiles={message.id === streamingMessageId ? currentOutputFiles : undefined}
              />
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t px-6 py-4 shrink-0">
        <div className="max-w-4xl mx-auto">
          {/* Uploaded Files Display */}
          {uploadedFiles.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {uploadedFiles.map((file) => (
                <div
                  key={file.file_id}
                  className="flex items-center gap-1 bg-muted rounded px-2 py-1 text-sm"
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
              <span className="text-sm text-muted-foreground">
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

      {/* Reset Confirmation Dialog */}
      <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset Everything</AlertDialogTitle>
            <AlertDialogDescription>
              Reset everything (messages, files, skills, tools, MCP servers, max turns) and start fresh?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                resetAll();
                setShowResetDialog(false);
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Reset
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

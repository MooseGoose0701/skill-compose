"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { RotateCcw, Paperclip, X, Wrench, Plug, ChevronDown, ChevronUp, Square, Bot, Cpu, Maximize2, Server, Navigation, Plus, Settings } from "lucide-react";
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
import { skillsApi, agentApi, mcpApi, toolsApi, agentPresetsApi, modelsApi, executorsApi } from "@/lib/api";
import type { StreamEvent } from "@/lib/api";
import { useChatStore, REQUIRED_TOOLS } from "@/stores/chat-store";
import { useChatSessionRestore } from "@/hooks/use-chat-session";
import { useChatEngine } from "@/hooks/use-chat-engine";
import { ChatMessageItem } from "./chat-message";
import { useTranslation } from "@/i18n/client";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  defaultSkills?: string[];
}

export function ChatPanel({ isOpen, onClose, defaultSkills = [] }: ChatPanelProps) {
  const { t } = useTranslation('chat');
  const { t: tc } = useTranslation('common');

  // Use zustand store for persistence
  const {
    messages,
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

  const [showConfigPanel, setShowConfigPanel] = React.useState(false);
  const [showToolsPanel, setShowToolsPanel] = React.useState(false);
  const [showResetDialog, setShowResetDialog] = React.useState(false);

  // ── Shared chat engine ──
  const engine = useChatEngine({
    messageAdapter: {
      getMessages: () => useChatStore.getState().messages,
      addMessage,
      updateMessage,
      removeMessages,
      getIsRunning: () => useChatStore.getState().isRunning,
      setIsRunning,
      getUploadedFiles: () => useChatStore.getState().uploadedFiles,
      clearUploadedFiles,
      addUploadedFile,
      removeUploadedFile,
    },
    streamAdapter: {
      runStream: async (request, agentFiles, onEvent, signal) => {
        const state = useChatStore.getState();
        let currentSessionId = state.sessionId;
        if (!currentSessionId) {
          currentSessionId = crypto.randomUUID();
          setSessionId(currentSessionId);
        }

        const currentAgentPreset = state.selectedAgentPreset;
        const currentModelProvider = state.selectedModelProvider;
        const currentModelName = state.selectedModelName;

        let agentRequest: import("@/lib/api").AgentRequest;

        if (currentAgentPreset) {
          agentRequest = {
            request,
            session_id: currentSessionId,
            agent_id: currentAgentPreset,
            uploaded_files: agentFiles,
            model_provider: currentModelProvider || undefined,
            model_name: currentModelName || undefined,
          };
        } else {
          const currentSkills = state.selectedSkills;
          const currentMcpServers = state.selectedMcpServers;
          const currentTools = state.selectedTools;
          const currentSystemPrompt = state.systemPrompt;
          const currentExecutorId = state.selectedExecutorId;

          const skillsList = currentSkills.length > 0 ? currentSkills : undefined;
          const mcpServersList = (currentMcpServers === null || currentMcpServers.length === 0) ? undefined : currentMcpServers;
          const toolsList = currentTools && currentTools.length > 0 ? currentTools : undefined;

          agentRequest = {
            request,
            session_id: currentSessionId,
            skills: skillsList,
            allowed_tools: toolsList,
            max_turns: state.maxTurns,
            uploaded_files: agentFiles,
            equipped_mcp_servers: mcpServersList,
            system_prompt: currentSystemPrompt || undefined,
            model_provider: currentModelProvider || undefined,
            model_name: currentModelName || undefined,
            executor_id: currentExecutorId || undefined,
          };
        }

        await agentApi.runStream(agentRequest, (event: StreamEvent) => onEvent(event), signal);
      },
      steer: async (traceId, message) => {
        await agentApi.steerAgent(traceId, message);
      },
    },
    onSessionId: (id) => setSessionId(id),
  });

  // Fetch available data
  const { data: skillsData } = useQuery({ queryKey: ["registry-skills-list"], queryFn: () => skillsApi.list() });
  const skills = (skillsData?.skills || []).filter(s => s.skill_type === 'user');

  const { data: toolsData } = useQuery({ queryKey: ["tools-list"], queryFn: () => toolsApi.list() });
  const tools = toolsData?.tools || [];

  const { data: mcpData } = useQuery({ queryKey: ["mcp-servers"], queryFn: () => mcpApi.listServers() });
  const mcpServers = mcpData?.servers || [];

  const { data: agentPresetsData } = useQuery({ queryKey: ["agent-presets-user"], queryFn: () => agentPresetsApi.list({ is_system: false }) });
  const agentPresets = agentPresetsData?.presets || [];

  const { data: modelsData } = useQuery({ queryKey: ["models-providers"], queryFn: () => modelsApi.listProviders() });
  const modelProviders = modelsData?.providers || [];

  const { data: executorsData } = useQuery({ queryKey: ["executors-list"], queryFn: () => executorsApi.list() });
  const onlineExecutors = (executorsData?.executors || []).filter(e => e.status === 'online');

  // Auto-scroll to bottom
  React.useEffect(() => {
    engine.messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Update selected skills when defaultSkills changes (from skill detail page)
  React.useEffect(() => {
    if (defaultSkills.length > 0) {
      setSelectedSkills(defaultSkills);
    }
  }, [defaultSkills, setSelectedSkills]);

  // Initialize selected tools with all tools selected by default
  React.useEffect(() => {
    if (tools.length > 0 && selectedTools === null) {
      setSelectedTools(tools.map((tool) => tool.name));
    }
  }, [tools, selectedTools, setSelectedTools]);

  // Initialize selected MCP servers - default_enabled servers are auto-selected
  React.useEffect(() => {
    if (mcpServers.length > 0 && selectedMcpServers === null) {
      setSelectedMcpServers(mcpServers.filter((s) => s.default_enabled).map((s) => s.name));
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

  const handleOpenFullscreen = () => {
    window.open("/chat", "_blank", "noopener,noreferrer");
  };

  const applyPreset = (presetId: string) => {
    const preset = agentPresets.find((p) => p.id === presetId);
    if (!preset) return;
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
    setSelectedExecutorId(preset.executor_id || null);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed right-0 top-0 h-full w-full sm:w-[480px] bg-background border-l shadow-lg flex flex-col z-50">
      {/* Header */}
      <div className="p-4 border-b flex items-center justify-between">
        <h2 className="font-semibold">{t('chatPanel')}</h2>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => newSession()} disabled={messages.length === 0 || isRunning} title={t('newChat')}>
            <Plus className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => !isRunning && setShowResetDialog(true)} disabled={isRunning} title={t('resetEverything')}>
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleOpenFullscreen} title={t('openFullscreen')}>
            <Maximize2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose}>
            {t('close')}
          </Button>
        </div>
      </div>

      {/* Compact Config Bar */}
      <div className="px-4 py-2 border-b bg-muted/30 flex items-center gap-2 text-xs min-w-0">
        {/* Agent Selector */}
        <Bot className="h-3.5 w-3.5 text-primary shrink-0" />
        <select
          value={selectedAgentPreset || ""}
          onChange={(e) => {
            const presetId = e.target.value;
            if (!presetId) { setSelectedAgentPreset(null); setSystemPrompt(null); }
            else applyPreset(presetId);
          }}
          className="h-6 text-xs px-1.5 rounded border bg-background min-w-0 max-w-[130px] truncate"
          title={t('configuration.agent')}
        >
          <option value="">{t('configuration.customConfig')}</option>
          {agentPresets.map((preset) => (
            <option key={preset.id} value={preset.id}>{preset.name}</option>
          ))}
        </select>

        <span className="text-muted-foreground/40 select-none">|</span>

        {/* Model Selector */}
        <Cpu className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <select
          value={selectedModelProvider && selectedModelName ? `${selectedModelProvider}/${selectedModelName}` : ""}
          onChange={(e) => {
            const value = e.target.value;
            if (!value) { setSelectedModel(null, null); }
            else { const [provider, ...p] = value.split('/'); setSelectedModel(provider, p.join('/')); }
            setSelectedAgentPreset(null);
          }}
          className="h-6 text-xs px-1.5 rounded border bg-background min-w-0 flex-1 truncate"
          title={t('configuration.model')}
        >
          <option value="">{t('defaultModel')}</option>
          {modelProviders.map((provider) => (
            <optgroup key={provider.name} label={provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}>
              {provider.models.map((model) => (
                <option key={model.key} value={model.key}>{model.display_name}</option>
              ))}
            </optgroup>
          ))}
        </select>

        {/* Config Toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowConfigPanel(!showConfigPanel)}
          className={`h-6 w-6 p-0 shrink-0 ${showConfigPanel ? 'text-primary' : ''}`}
          title={t('config')}
        >
          <Settings className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Expanded Config Panel */}
      {showConfigPanel && (
        <div className="px-4 py-3 border-b bg-muted/20 space-y-3 text-xs max-h-[40vh] overflow-y-auto">
          {selectedAgentPreset && (
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
              <span>{t('configManagedByPreset')}</span>
              <Link href="/agents" className="text-primary hover:underline">{t('manage')}</Link>
            </div>
          )}

          {/* Executor */}
          {onlineExecutors.length > 0 && (
            <div className="flex items-center gap-2">
              <Server className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <span className="text-muted-foreground shrink-0">{t('configuration.executor')}:</span>
              <select
                value={selectedExecutorId || ""}
                onChange={(e) => { setSelectedExecutorId(e.target.value || null); setSelectedAgentPreset(null); }}
                className="h-6 text-xs px-1.5 rounded border bg-background flex-1"
              >
                <option value="">{t('configuration.executorLocal')}</option>
                {onlineExecutors.map((executor) => (
                  <option key={executor.id} value={executor.id}>{executor.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Turns + Skills */}
          <div className={`flex items-center gap-3 ${selectedAgentPreset ? 'opacity-50 pointer-events-none' : ''}`}>
            <div className="flex items-center gap-1.5">
              <span className="text-muted-foreground">{t('configuration.turns')}</span>
              <Input
                type="number" min={1} max={60000} value={maxTurns}
                onChange={(e) => { setMaxTurns(parseInt(e.target.value) || 60); setSelectedAgentPreset(null); }}
                className="w-14 h-6 text-xs px-2"
              />
            </div>
            <div className="flex items-center gap-1.5 flex-1 min-w-0">
              <span className="text-muted-foreground shrink-0">{t('configuration.skills')}</span>
              <MultiSelect
                options={skills.map((skill) => ({ value: skill.name, label: skill.name, description: skill.description?.slice(0, 50) }))}
                selected={selectedSkills}
                onChange={(s) => { setSelectedSkills(s); setSelectedAgentPreset(null); }}
                placeholder={t('configuration.selectSkills')}
                emptyText="None"
                className="flex-1 min-w-0"
                size="sm"
              />
            </div>
          </div>

          {/* Tools/MCP Toggle */}
          <div className={selectedAgentPreset ? 'opacity-50 pointer-events-none' : ''}>
            <Button variant="ghost" size="sm" onClick={() => setShowToolsPanel(!showToolsPanel)} className="h-6 px-2 text-xs gap-1">
              <Wrench className="h-3 w-3" />
              {t('configuration.tools')} ({(selectedTools || []).length}/{tools.length})
              {mcpServers.length > 0 && (
                <span className="text-muted-foreground">+ MCP ({(selectedMcpServers || []).length})</span>
              )}
              {showToolsPanel ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            </Button>

            {/* Tools/MCP Chips */}
            {showToolsPanel && (
              <div className="mt-2 space-y-3">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Wrench className="h-3 w-3 text-muted-foreground" />
                    <span className="text-xs font-medium">{t('builtinTools')}</span>
                    <span className="text-xs text-muted-foreground">({(selectedTools || []).length}/{tools.length})</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {tools.map((tool) => {
                      const isRequired = REQUIRED_TOOLS.includes(tool.name);
                      const isSelected = (selectedTools || []).includes(tool.name);
                      return (
                        <button
                          key={tool.id}
                          onClick={() => {
                            if (isRequired) return;
                            const cur = selectedTools || [];
                            setSelectedTools(isSelected ? cur.filter((t) => t !== tool.name) : [...cur, tool.name]);
                            setSelectedAgentPreset(null);
                          }}
                          disabled={isRequired}
                          className={`px-1.5 py-0.5 text-[11px] rounded border transition-colors ${isRequired ? 'bg-primary/20 border-primary/50 text-primary cursor-not-allowed' : isSelected ? 'bg-primary/10 border-primary text-primary hover:bg-primary/20' : 'bg-background border-border text-muted-foreground hover:bg-muted'}`}
                          title={isRequired ? `${tool.name} (required)` : tool.description}
                        >
                          {tool.name}{isRequired && '*'}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {mcpServers.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Plug className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs font-medium">{t('configuration.mcpServers')}</span>
                      <span className="text-xs text-muted-foreground">({(selectedMcpServers || []).length}/{mcpServers.length})</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {mcpServers.map((server) => {
                        const isSelected = (selectedMcpServers || []).includes(server.name);
                        return (
                          <button
                            key={server.name}
                            onClick={() => {
                              const cur = selectedMcpServers || [];
                              setSelectedMcpServers(isSelected ? cur.filter((s) => s !== server.name) : [...cur, server.name]);
                              setSelectedAgentPreset(null);
                            }}
                            className={`px-1.5 py-0.5 text-[11px] rounded border transition-colors ${isSelected ? 'bg-purple-500/10 border-purple-500 text-purple-600 hover:bg-purple-500/20' : 'bg-background border-border text-muted-foreground hover:bg-muted'}`}
                            title={server.description}
                          >
                            {server.display_name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                <p className="text-[10px] text-muted-foreground">
                  {t('requiredToolsNote')} {t('mcpDefaultNote')}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            <p>{t('startConversation')}.</p>
            <p className="text-sm mt-2">{t('selectSkillsHint')}</p>
            <p className="text-sm mt-1">{t('multiTurnHint')}</p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessageItem
              key={message.id}
              message={message}
              streamingContent={message.id === engine.streamingMessageId ? engine.streamingContent : null}
              streamingEvents={message.id === engine.streamingMessageId ? engine.streamingEvents : undefined}
              streamingOutputFiles={message.id === engine.streamingMessageId ? engine.currentOutputFiles : undefined}
            />
          ))
        )}
        <div ref={engine.messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t">
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
                <Square className="h-4 w-4 mr-1" />
                {t('stop')}
              </Button>
              <Button onClick={engine.handleSubmit} disabled={!engine.input.trim()} size="sm">
                <Navigation className="h-4 w-4 mr-1" />
                {t('steering.button')}
              </Button>
            </div>
          ) : (
            <Button onClick={engine.handleSubmit} disabled={!engine.input.trim()}>
              {t('send')}
            </Button>
          )}
        </div>
      </div>

      {/* Reset Confirmation Dialog */}
      <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('resetEverything')}</AlertDialogTitle>
            <AlertDialogDescription>{t('resetDescription')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => { resetAll(); setShowResetDialog(false); }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {t('reset')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

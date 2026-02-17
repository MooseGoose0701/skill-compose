"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  RotateCcw, Paperclip, X, Wrench, Plug, ChevronDown, ChevronUp, Square, Bot, Cpu, Server,
  MessageSquare, Home, Settings, Navigation, Plus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { MultiSelect } from "@/components/ui/multi-select";
import { skillsApi, agentApi, mcpApi, toolsApi, agentPresetsApi, modelsApi, executorsApi } from "@/lib/api";
import type { StreamEvent } from "@/lib/api";
import { useChatStore, REQUIRED_TOOLS } from "@/stores/chat-store";
import { useChatSessionRestore } from "@/hooks/use-chat-session";
import { useChatEngine } from "@/hooks/use-chat-engine";
import { ChatMessageItem } from "@/components/chat/chat-message";
import { useTranslation } from "@/i18n/client";

export default function FullscreenChatPage() {
  const { t } = useTranslation('chat');
  const { t: tc } = useTranslation('common');

  const {
    messages, selectedSkills, selectedTools, selectedMcpServers, isRunning, maxTurns,
    uploadedFiles, selectedAgentPreset, systemPrompt,
    addMessage, updateMessage, removeMessages, newSession, resetAll,
    setSessionId, setSelectedSkills, setSelectedTools, setSelectedMcpServers,
    setIsRunning, setMaxTurns, addUploadedFile, removeUploadedFile, clearUploadedFiles,
    setSelectedAgentPreset, setSystemPrompt,
    selectedModelProvider, selectedModelName, setSelectedModel,
    selectedExecutorId, setSelectedExecutorId,
  } = useChatStore();

  useChatSessionRestore();

  const [showConfig, setShowConfig] = React.useState(false);
  const [showToolsPanel, setShowToolsPanel] = React.useState(false);
  const [showResetDialog, setShowResetDialog] = React.useState(false);

  // ── Shared chat engine ──
  const engine = useChatEngine({
    messageAdapter: {
      getMessages: () => useChatStore.getState().messages,
      addMessage, updateMessage, removeMessages,
      getIsRunning: () => useChatStore.getState().isRunning,
      setIsRunning,
      getUploadedFiles: () => useChatStore.getState().uploadedFiles,
      clearUploadedFiles, addUploadedFile, removeUploadedFile,
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
            request, session_id: currentSessionId, agent_id: currentAgentPreset,
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

          agentRequest = {
            request, session_id: currentSessionId,
            skills: currentSkills.length > 0 ? currentSkills : undefined,
            allowed_tools: currentTools && currentTools.length > 0 ? currentTools : undefined,
            max_turns: state.maxTurns,
            uploaded_files: agentFiles,
            equipped_mcp_servers: (currentMcpServers === null || currentMcpServers.length === 0) ? undefined : currentMcpServers,
            system_prompt: currentSystemPrompt || undefined,
            model_provider: currentModelProvider || undefined,
            model_name: currentModelName || undefined,
            executor_id: currentExecutorId || undefined,
          };
        }

        await agentApi.runStream(agentRequest, (event: StreamEvent) => onEvent(event), signal);
      },
      steer: async (traceId, message) => { await agentApi.steerAgent(traceId, message); },
    },
    onSessionId: (id) => setSessionId(id),
  });

  // Fetch data
  const { data: skillsData } = useQuery({ queryKey: ["registry-skills-list"], queryFn: () => skillsApi.list() });
  const skills = (skillsData?.skills || []).filter(s => s.skill_type === 'user');

  const { data: toolsData } = useQuery({ queryKey: ["tools-list"], queryFn: () => toolsApi.list() });
  const tools = toolsData?.tools || [];

  const { data: mcpData } = useQuery({ queryKey: ["mcp-servers"], queryFn: () => mcpApi.listServers() });
  const mcpServers = mcpData?.servers || [];

  const { data: agentPresetsData, isLoading: isLoadingAgents } = useQuery({ queryKey: ["agent-presets-user"], queryFn: () => agentPresetsApi.list({ is_system: false }) });
  const agentPresets = agentPresetsData?.presets || [];

  const { data: modelsData, isLoading: isLoadingModels } = useQuery({ queryKey: ["models-providers"], queryFn: () => modelsApi.listProviders() });
  const modelProviders = modelsData?.providers || [];

  const { data: executorsData } = useQuery({ queryKey: ["executors-list"], queryFn: () => executorsApi.list() });
  const onlineExecutors = (executorsData?.executors || []).filter(e => e.status === 'online');

  // Auto-scroll
  React.useEffect(() => {
    engine.messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, engine.streamingContent]);

  // Init tools
  React.useEffect(() => {
    if (tools.length > 0 && selectedTools === null) {
      setSelectedTools(tools.map((t) => t.name));
    }
  }, [tools, selectedTools, setSelectedTools]);

  // Init MCP
  React.useEffect(() => {
    if (mcpServers.length > 0 && selectedMcpServers === null) {
      setSelectedMcpServers(mcpServers.filter((s) => s.default_enabled).map((s) => s.name));
    }
  }, [mcpServers, selectedMcpServers, setSelectedMcpServers]);

  // Sync preset systemPrompt
  React.useEffect(() => {
    if (agentPresets.length > 0 && selectedAgentPreset) {
      const preset = agentPresets.find((p) => p.id === selectedAgentPreset);
      if (preset && preset.system_prompt && !systemPrompt) setSystemPrompt(preset.system_prompt);
    }
  }, [agentPresets, selectedAgentPreset, systemPrompt, setSystemPrompt]);

  const applyPreset = (presetId: string) => {
    const preset = agentPresets.find((p) => p.id === presetId);
    if (!preset) return;
    setSelectedAgentPreset(preset.id);
    setSelectedSkills(preset.skill_ids || []);
    setMaxTurns(preset.max_turns);
    setSystemPrompt(preset.system_prompt || null);
    if (preset.builtin_tools === null && tools.length > 0) setSelectedTools(tools.map(t => t.name));
    else if (preset.builtin_tools && preset.builtin_tools.length > 0) setSelectedTools(preset.builtin_tools);
    else setSelectedTools([]);
    setSelectedMcpServers(preset.mcp_servers || []);
    setSelectedModel(preset.model_provider || null, preset.model_name || null);
    setSelectedExecutorId(preset.executor_id || null);
  };

  const currentAgentName = selectedAgentPreset
    ? agentPresets.find((p) => p.id === selectedAgentPreset)?.name || "Custom"
    : t('configuration.customConfig');

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b px-6 py-4 flex items-center gap-3 shrink-0">
        <MessageSquare className="h-6 w-6 text-primary" />
        <div className="flex-1">
          <h1 className="font-semibold text-lg">{t('title')}</h1>
          <p className="text-sm text-muted-foreground">
            {currentAgentName}
            {selectedModelName && ` \u2022 ${selectedModelName}`}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => setShowConfig(!showConfig)} title={t('config')}>
          <Settings className="h-4 w-4 mr-1" />
          {t('config')}
          {showConfig ? <ChevronUp className="h-4 w-4 ml-1" /> : <ChevronDown className="h-4 w-4 ml-1" />}
        </Button>
        <Button variant="outline" size="sm" onClick={() => newSession()} disabled={messages.length === 0 || isRunning} title={t('newChat')}>
          <Plus className="h-4 w-4 mr-1" />
          {t('newChat')}
        </Button>
        <Button variant="outline" size="sm" onClick={() => !isRunning && setShowResetDialog(true)} disabled={isRunning} title={t('resetEverything')}>
          <RotateCcw className="h-4 w-4 mr-1" />
          {t('resetAll')}
        </Button>
        <Link href="/">
          <Button variant="outline" size="sm" title={t('home')}>
            <Home className="h-4 w-4 mr-1" />
            {t('home')}
          </Button>
        </Link>
      </div>

      {/* Configuration Panel (collapsible) */}
      {showConfig && (
        <div className="border-b bg-muted/30 px-6 py-4 space-y-4 shrink-0">
          <div className="flex flex-wrap items-center gap-4">
            {/* Agent Selector */}
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{t('configuration.agent')}:</span>
              <select
                value={selectedAgentPreset || ""}
                onChange={(e) => { if (!e.target.value) { setSelectedAgentPreset(null); setSystemPrompt(null); } else applyPreset(e.target.value); }}
                className="h-8 text-sm px-2 rounded border bg-background"
                disabled={isLoadingAgents}
              >
                {isLoadingAgents ? <option value="">{tc('actions.loading')}...</option> : (
                  <>
                    <option value="">{t('configuration.customConfig')}</option>
                    {agentPresets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </>
                )}
              </select>
            </div>
            {/* Model Selector */}
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{t('configuration.model')}:</span>
              <select
                value={selectedModelProvider && selectedModelName ? `${selectedModelProvider}/${selectedModelName}` : ""}
                onChange={(e) => {
                  const v = e.target.value;
                  if (!v) setSelectedModel(null, null);
                  else { const [p, ...m] = v.split('/'); setSelectedModel(p, m.join('/')); }
                  setSelectedAgentPreset(null);
                }}
                className="h-8 text-sm px-2 rounded border bg-background"
                disabled={isLoadingModels}
              >
                {isLoadingModels ? <option value="">{tc('actions.loading')}...</option> : (
                  <>
                    <option value="">{t('defaultModel')}</option>
                    {modelProviders.map((provider) => (
                      <optgroup key={provider.name} label={provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}>
                        {provider.models.map((model) => <option key={model.key} value={model.key}>{model.display_name}</option>)}
                      </optgroup>
                    ))}
                  </>
                )}
              </select>
            </div>
            {/* Executor */}
            {onlineExecutors.length > 0 && (
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">{t('configuration.executor')}:</span>
                <select
                  value={selectedExecutorId || ""}
                  onChange={(e) => { setSelectedExecutorId(e.target.value || null); setSelectedAgentPreset(null); }}
                  className="h-8 text-sm px-2 rounded border bg-background"
                >
                  <option value="">{t('configuration.executorLocal')}</option>
                  {onlineExecutors.map((ex) => <option key={ex.id} value={ex.id}>{ex.name}</option>)}
                </select>
              </div>
            )}
          </div>

          {/* Skills and Turns */}
          <div className={`flex flex-wrap items-center gap-4 ${selectedAgentPreset ? 'opacity-50' : ''}`}>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{t('configuration.turns')}:</span>
              <Input type="number" min={1} max={60000} value={maxTurns}
                onChange={(e) => { setMaxTurns(parseInt(e.target.value) || 60); setSelectedAgentPreset(null); }}
                className="w-16 h-8 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{t('configuration.skills')}:</span>
              <MultiSelect
                options={skills.map((s) => ({ value: s.name, label: s.name, description: s.description?.slice(0, 50) }))}
                selected={selectedSkills}
                onChange={(s) => { setSelectedSkills(s); setSelectedAgentPreset(null); }}
                placeholder={t('configuration.selectSkills')} emptyText="None"
                className="min-w-[150px]" size="sm"
              />
            </div>
            <Button variant="outline" size="sm" onClick={() => setShowToolsPanel(!showToolsPanel)} className="gap-1">
              <Wrench className="h-4 w-4" />
              {t('configuration.tools')} ({(selectedTools || []).length}/{tools.length})
              {mcpServers.length > 0 && <span className="text-muted-foreground">+ MCP ({(selectedMcpServers || []).length})</span>}
              {showToolsPanel ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>

          {/* Tools/MCP Panel */}
          {showToolsPanel && (
            <div className={`pt-3 border-t ${selectedAgentPreset ? 'opacity-50' : ''}`}>
              <div className="mb-3">
                <div className="flex items-center gap-2 mb-2">
                  <Wrench className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{t('builtinTools')}</span>
                  <span className="text-sm text-muted-foreground">({(selectedTools || []).length}/{tools.length} {t('selected')})</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {tools.map((tool) => {
                    const isRequired = REQUIRED_TOOLS.includes(tool.name);
                    const isSelected = (selectedTools || []).includes(tool.name);
                    return (
                      <button key={tool.id}
                        onClick={() => { if (isRequired) return; const cur = selectedTools || []; setSelectedTools(isSelected ? cur.filter((t) => t !== tool.name) : [...cur, tool.name]); setSelectedAgentPreset(null); }}
                        disabled={isRequired}
                        className={`px-2 py-1 text-sm rounded-md border transition-colors ${isRequired ? 'bg-primary/20 border-primary/50 text-primary cursor-not-allowed' : isSelected ? 'bg-primary/10 border-primary text-primary hover:bg-primary/20' : 'bg-background border-border text-muted-foreground hover:bg-muted'}`}
                        title={isRequired ? `${tool.name} (required)` : tool.description}
                      >
                        {tool.name}
                        {isRequired && <span className="ml-1 text-xs">*</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
              {mcpServers.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Plug className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{t('configuration.mcpServers')}</span>
                    <span className="text-sm text-muted-foreground">({(selectedMcpServers || []).length}/{mcpServers.length} {t('selected')})</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {mcpServers.map((server) => {
                      const isSelected = (selectedMcpServers || []).includes(server.name);
                      return (
                        <button key={server.name}
                          onClick={() => { const cur = selectedMcpServers || []; setSelectedMcpServers(isSelected ? cur.filter((s) => s !== server.name) : [...cur, server.name]); setSelectedAgentPreset(null); }}
                          className={`px-2 py-1 text-sm rounded-md border transition-colors ${isSelected ? 'bg-purple-500/10 border-purple-500 text-purple-600 hover:bg-purple-500/20' : 'bg-background border-border text-muted-foreground hover:bg-muted'}`}
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
            <p className="text-lg">{t('startConversation')}</p>
            <p className="text-sm mt-2">{t('typeMessageToBegin')}</p>
            {!showConfig && <p className="text-sm mt-1">{t('clickConfigToCustomize')}</p>}
          </div>
        ) : (
          messages.map((message) => (
            <div key={message.id} className="max-w-4xl mx-auto">
              <ChatMessageItem
                message={message}
                streamingContent={message.id === engine.streamingMessageId ? engine.streamingContent : null}
                streamingEvents={message.id === engine.streamingMessageId ? engine.streamingEvents : undefined}
                streamingOutputFiles={message.id === engine.streamingMessageId ? engine.currentOutputFiles : undefined}
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
                <div key={file.file_id} className="flex items-center gap-1 bg-muted rounded px-2 py-1 text-sm">
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
              <span className="text-sm text-muted-foreground">{t('enterToSend')}</span>
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

      {/* Reset Dialog */}
      <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('resetEverything')}</AlertDialogTitle>
            <AlertDialogDescription>{t('resetDescription')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => { resetAll(); setShowResetDialog(false); }} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('reset')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

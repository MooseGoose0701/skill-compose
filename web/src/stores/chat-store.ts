'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { StepInfo, UploadedFile, OutputFileInfo } from '@/lib/api';
import type { StreamEventRecord } from '@/types/stream-events';

export interface AttachedFile {
  file_id: string;
  filename: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  steps?: StepInfo[];
  isLoading?: boolean;
  error?: string;
  traceId?: string;
  outputFiles?: OutputFileInfo[];
  rawAnswer?: string;  // Agent's actual final answer (without stream UI formatting)
  streamEvents?: StreamEventRecord[];  // Structured stream events for rich UI rendering
  attachedFiles?: AttachedFile[];  // Files attached to user messages
}

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;  // Server-side session ID
  selectedSkills: string[];
  selectedTools: string[] | null;  // null = not initialized, will auto-select all tools
  selectedMcpServers: string[] | null;  // null = not initialized, will auto-select default_enabled
  isRunning: boolean;
  maxTurns: number;
  uploadedFiles: UploadedFile[];
  selectedAgentPreset: string | null;  // Currently selected agent preset ID
  systemPrompt: string | null;  // Custom system prompt from agent preset
  selectedModelProvider: string | null;  // LLM provider: anthropic, openrouter, openai, google
  selectedModelName: string | null;  // Model name/ID
  selectedExecutorName: string | null;  // Executor name for code execution

  // Actions
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  removeMessages: (ids: string[]) => void;
  clearMessages: () => void;
  setSessionId: (id: string | null) => void;
  newSession: () => void;  // Clear messages + sessionId + files, keep config
  setSelectedSkills: (skills: string[]) => void;
  toggleSkill: (skillName: string) => void;
  setSelectedTools: (tools: string[]) => void;
  toggleTool: (toolName: string, required?: boolean) => void;
  setSelectedMcpServers: (servers: string[]) => void;
  toggleMcpServer: (serverName: string) => void;
  setIsRunning: (running: boolean) => void;
  setMaxTurns: (turns: number) => void;
  addUploadedFile: (file: UploadedFile) => void;
  removeUploadedFile: (fileId: string) => void;
  clearUploadedFiles: () => void;
  resetAll: () => void;  // Reset everything to defaults
  setSelectedAgentPreset: (presetId: string | null) => void;  // Set selected agent preset
  setSystemPrompt: (prompt: string | null) => void;  // Set custom system prompt
  setSelectedModel: (provider: string | null, name: string | null) => void;  // Set model
  setSelectedExecutorName: (id: string | null) => void;  // Set executor
}

// Required tools that cannot be deselected
export const REQUIRED_TOOLS = ['list_skills', 'get_skill'];

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      messages: [],
      sessionId: null,
      selectedSkills: [],
      selectedTools: null,  // null = not initialized, will auto-select all tools
      selectedMcpServers: null,  // null = not initialized, will auto-select default_enabled
      isRunning: false,
      maxTurns: 60,
      uploadedFiles: [],
      selectedAgentPreset: null,
      systemPrompt: null,
      selectedModelProvider: null,  // null = use default
      selectedModelName: null,  // null = use default
      selectedExecutorName: null,  // null = local execution

      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message],
        })),

      updateMessage: (id, updates) =>
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id ? { ...msg, ...updates } : msg
          ),
        })),

      removeMessages: (ids) =>
        set((state) => ({
          messages: state.messages.filter((msg) => !ids.includes(msg.id)),
        })),

      clearMessages: () => set({ messages: [] }),

      setSessionId: (id) => set({ sessionId: id }),

      newSession: () => set({ messages: [], sessionId: null, uploadedFiles: [] }),

      setSelectedSkills: (skills) => set({ selectedSkills: skills }),

      toggleSkill: (skillName) =>
        set((state) => {
          const skills = new Set(state.selectedSkills);
          if (skills.has(skillName)) {
            skills.delete(skillName);
          } else {
            skills.add(skillName);
          }
          return { selectedSkills: Array.from(skills) };
        }),

      setSelectedTools: (tools) => set({ selectedTools: tools }),

      toggleTool: (toolName, required = false) =>
        set((state) => {
          // Don't allow toggling required tools
          if (required || REQUIRED_TOOLS.includes(toolName)) return state;
          const tools = new Set(state.selectedTools || []);
          if (tools.has(toolName)) {
            tools.delete(toolName);
          } else {
            tools.add(toolName);
          }
          return { selectedTools: Array.from(tools) };
        }),

      setSelectedMcpServers: (servers) => set({ selectedMcpServers: servers }),

      toggleMcpServer: (serverName) =>
        set((state) => {
          const servers = new Set(state.selectedMcpServers || []);
          if (servers.has(serverName)) {
            servers.delete(serverName);
          } else {
            servers.add(serverName);
          }
          return { selectedMcpServers: Array.from(servers) };
        }),

      setIsRunning: (running) => set({ isRunning: running }),

      setMaxTurns: (turns) => set({ maxTurns: Math.max(1, Math.min(60000, turns)) }),

      addUploadedFile: (file) =>
        set((state) => ({
          uploadedFiles: [...state.uploadedFiles, file],
        })),

      removeUploadedFile: (fileId) =>
        set((state) => ({
          uploadedFiles: state.uploadedFiles.filter((f) => f.file_id !== fileId),
        })),

      clearUploadedFiles: () => set({ uploadedFiles: [] }),

      resetAll: () => set({
        messages: [],
        sessionId: null,
        selectedSkills: [],
        selectedTools: null,  // Will trigger auto-select all tools
        selectedMcpServers: null,  // Will trigger auto-select default_enabled
        maxTurns: 60,
        uploadedFiles: [],
        isRunning: false,
        selectedAgentPreset: null,
        systemPrompt: null,
        selectedModelProvider: null,
        selectedModelName: null,
        selectedExecutorName: null,
      }),

      setSelectedAgentPreset: (presetId) => set({ selectedAgentPreset: presetId }),

      setSystemPrompt: (prompt) => set({ systemPrompt: prompt }),

      setSelectedModel: (provider, name) => set({
        selectedModelProvider: provider,
        selectedModelName: name
      }),

      setSelectedExecutorName: (id) => set({ selectedExecutorName: id }),
    }),
    {
      name: 'chat-storage',
      version: 11, // Increment this when making breaking changes
      partialize: (state) => ({
        // Messages are NOT persisted — server session is source of truth
        sessionId: state.sessionId,
        selectedSkills: state.selectedSkills,
        selectedTools: state.selectedTools,
        selectedMcpServers: state.selectedMcpServers,
        maxTurns: state.maxTurns,
        selectedAgentPreset: state.selectedAgentPreset,
        systemPrompt: state.systemPrompt,
        selectedModelProvider: state.selectedModelProvider,
        selectedModelName: state.selectedModelName,
        selectedExecutorName: state.selectedExecutorName,
      }),
      // Migration from old versions
      migrate: (persistedState: unknown, version: number) => {
        const state = persistedState as Partial<ChatState>;

        // v0/v1/v2 -> v3: Reset tools and MCP servers to null for re-initialization
        if (version < 3) {
          state.selectedTools = null;
          state.selectedMcpServers = null;
        }

        // v3 -> v4: Reset MCP servers to pick up new default_enabled (Fetch, Time)
        if (version < 4) {
          state.selectedMcpServers = null;
        }

        // v4 -> v5: Add selectedAgentPreset
        if (version < 5) {
          state.selectedAgentPreset = null;
        }

        // v5 -> v6: Add systemPrompt
        if (version < 6) {
          state.systemPrompt = null;
        }

        // v6 -> v7: Add model selection
        if (version < 7) {
          state.selectedModelProvider = null;
          state.selectedModelName = null;
        }

        // v7 -> v8: Add streamEvents (no migration needed, field is optional)

        // v8 -> v9: Add selectedExecutorName
        if (version < 9) {
          state.selectedExecutorName = null;
        }

        // v9 -> v10: Add sessionId, messages no longer persisted (server is source of truth)
        if (version < 10) {
          (state as Record<string, unknown>).sessionId = null;
          state.messages = [];
        }

        // v10 -> v11: Rename selectedExecutorId → selectedExecutorName
        if (version < 11) {
          const raw = state as Record<string, unknown>;
          if ('selectedExecutorId' in raw) {
            raw.selectedExecutorName = null;  // Clear old UUID value
            delete raw.selectedExecutorId;
          }
        }

        return state as ChatState;
      },
    }
  )
);


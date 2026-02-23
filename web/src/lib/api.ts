/**
 * API Client for Skills Registry
 */

import type {
  Skill,
  SkillListResponse,
  SkillDetailResponse,
  SkillVersion,
  VersionListResponse,
  SkillChangelog,
  CreateSkillRequest,
  CreateVersionRequest,
  UpdateSkillRequest,
  Tool,
  ToolListResponse,
} from '@/types/skill';

// Helper to get backend API base URL
// NEXT_PUBLIC_API_URL can be 'http://localhost:62610' or 'http://localhost:62610/api/v1'
// We normalize it to always end with '/api/v1'
function getApiBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:62610';
  // Remove trailing slash if present
  const cleanUrl = baseUrl.replace(/\/$/, '');
  // Add /api/v1 if not already present
  if (cleanUrl.endsWith('/api/v1')) {
    return cleanUrl;
  }
  return `${cleanUrl}/api/v1`;
}

const BACKEND_API_BASE = getApiBaseUrl();

// Use backend URL directly for all APIs (works in Docker)
const API_BASE = `${BACKEND_API_BASE}/registry`;

// Export for pages that need direct API access
export { BACKEND_API_BASE };

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      error.detail || error.message || `HTTP ${response.status}`
    );
  }

  return response.json();
}

// Task types
interface CreateTaskResponse {
  task_id: string;
  status: string;
  message: string;
}

interface TaskStatusResponse {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  skill_name?: string;
  trace_id?: string;
  error?: string;
}

export interface UpdateFromSourceResult {
  success: boolean;
  skill_name: string;
  old_version: string | null;
  new_version: string | null;
  message: string;
  changes: string[] | null;
}

// Skills API
export const skillsApi = {
  list: async (params?: {
    status?: string;
    tags?: string[];
    category?: string;
    sort_by?: string;
    sort_order?: string;
    offset?: number;
    limit?: number;
  }): Promise<SkillListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.tags?.length) searchParams.set('tags', params.tags.join(','));
    if (params?.category) searchParams.set('category', params.category);
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    return fetchApi(`/skills${query ? `?${query}` : ''}`);
  },

  listTags: async (): Promise<string[]> => {
    return fetchApi('/tags');
  },

  listCategories: async (): Promise<string[]> => {
    return fetchApi('/categories');
  },

  togglePin: async (name: string): Promise<{ name: string; is_pinned: boolean }> => {
    return fetchApi(`/skills/${encodeURIComponent(name)}/toggle-pin`, {
      method: 'POST',
    });
  },

  get: async (name: string): Promise<SkillDetailResponse> => {
    return fetchApi(`/skills/${encodeURIComponent(name)}`);
  },

  create: async (data: CreateSkillRequest): Promise<CreateTaskResponse> => {
    return fetchApi('/skills', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  getTaskStatus: async (taskId: string): Promise<TaskStatusResponse> => {
    return fetchApi(`/tasks/${encodeURIComponent(taskId)}`);
  },

  update: async (name: string, data: UpdateSkillRequest): Promise<Skill> => {
    return fetchApi(`/skills/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: async (name: string): Promise<void> => {
    return fetchApi(`/skills/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
  },

  search: async (query: string): Promise<SkillListResponse> => {
    return fetchApi(`/skills/search?q=${encodeURIComponent(query)}`);
  },

  getEvolveTaskStatus: async (taskId: string): Promise<{
    task_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    skill_name?: string;
    new_version?: string;
    trace_id?: string;
    error?: string;
  }> => {
    const backendUrl = BACKEND_API_BASE;
    const response = await fetch(`${backendUrl}/registry/tasks/${encodeURIComponent(taskId)}`);

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Failed to get task status'
      );
    }

    return response.json();
  },

  syncFilesystem: async (name: string): Promise<{
    synced: boolean;
    old_version?: string;
    new_version?: string;
    changes_summary?: string;
  }> => {
    return fetchApi(`/skills/${encodeURIComponent(name)}/sync-filesystem`, {
      method: 'POST',
    });
  },

  listUnregistered: async (): Promise<{
    skills: Array<{ name: string; description: string | null; path: string; skill_type: string }>;
    total: number;
  }> => {
    return fetchApi('/unregistered-skills');
  },

  importLocal: async (skillNames: string[]): Promise<{
    results: Array<{ name: string; success: boolean; version?: string; error?: string }>;
    total_imported: number;
    total_failed: number;
  }> => {
    return fetchApi('/import-local', {
      method: 'POST',
      body: JSON.stringify({ skill_names: skillNames }),
    });
  },

  evolveViaTraces: async (name: string, params: {
    traceIds?: string[];
    feedback?: string;
  }): Promise<{
    task_id: string;
    status: string;
    message: string;
  }> => {
    // Call backend directly to avoid Next.js proxy timeout for long-running agent requests
    const backendUrl = BACKEND_API_BASE;
    const body: Record<string, unknown> = {};
    if (params.traceIds?.length) body.trace_ids = params.traceIds;
    if (params.feedback?.trim()) body.feedback = params.feedback.trim();

    const response = await fetch(`${backendUrl}/registry/skills/${encodeURIComponent(name)}/evolve-via-traces`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Evolution failed'
      );
    }

    return response.json();
  },

  // Icon management
  uploadIcon: async (skillName: string, file: File): Promise<{ skill_name: string; icon_url: string; message: string }> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/icon`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Icon upload failed'
      );
    }

    return response.json();
  },

  deleteIcon: async (skillName: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/icon`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Icon deletion failed'
      );
    }
  },

  generateIcon: async (skillName: string, prompt?: string): Promise<{ skill_name: string; icon_url: string; message: string }> => {
    const body: { prompt?: string } = {};
    if (prompt) body.prompt = prompt;

    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/generate-icon`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Icon generation failed'
      );
    }

    return response.json();
  },

  updateFromGitHub: async (skillName: string): Promise<{
    success: boolean;
    skill_name: string;
    old_version: string | null;
    new_version: string | null;
    message: string;
    changes: string[] | null;
  }> => {
    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/update-from-github`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Update from GitHub failed'
      );
    }

    return response.json();
  },

  updateFromSourceGitHub: async (skillName: string, url: string): Promise<UpdateFromSourceResult> => {
    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/update-from-source-github`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || error.message || 'Update from GitHub failed');
    }

    return response.json();
  },

  updateFromSourceFile: async (skillName: string, file: File): Promise<UpdateFromSourceResult> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/update-from-source-file`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || error.message || 'Update from file failed');
    }

    return response.json();
  },

  updateFromSourceFolder: async (skillName: string, files: FileList | File[]): Promise<UpdateFromSourceResult> => {
    const formData = new FormData();
    const fileArray = Array.from(files);
    for (const file of fileArray) {
      formData.append('files', file);
    }

    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/update-from-source-folder`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || error.message || 'Update from folder failed');
    }

    return response.json();
  },

  checkGithubUpdates: async (): Promise<{ results: Record<string, { has_update: boolean }> }> => {
    return fetchApi('/skills/check-github-updates', {
      method: 'POST',
    });
  },
};

// Versions API
export const versionsApi = {
  list: async (
    skillName: string,
    params?: { offset?: number; limit?: number }
  ): Promise<VersionListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    return fetchApi(
      `/skills/${encodeURIComponent(skillName)}/versions${query ? `?${query}` : ''}`
    );
  },

  get: async (skillName: string, version: string): Promise<SkillVersion> => {
    return fetchApi(
      `/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}`
    );
  },

  create: async (
    skillName: string,
    data: CreateVersionRequest
  ): Promise<SkillVersion> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/versions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  diff: async (
    skillName: string,
    fromVersion: string,
    toVersion: string,
    filePath?: string
  ): Promise<{ diff: string; from_version: string; to_version: string; file_path: string; old_content: string; new_content: string }> => {
    let url = `/skills/${encodeURIComponent(skillName)}/diff?from=${encodeURIComponent(fromVersion)}&to=${encodeURIComponent(toVersion)}`;
    if (filePath) {
      url += `&file_path=${encodeURIComponent(filePath)}`;
    }
    return fetchApi(url);
  },

  getVersionFiles: async (
    skillName: string,
    version: string
  ): Promise<{ version: string; files: Array<{ file_path: string; file_type: string; size_bytes?: number }> }> => {
    return fetchApi(
      `/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}/files`
    );
  },

  getVersionFileContent: async (
    skillName: string,
    version: string,
    filePath: string
  ): Promise<{ file_path: string; content: string }> => {
    return fetchApi(
      `/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}/files/${encodeURIComponent(filePath)}`
    );
  },

  rollback: async (
    skillName: string,
    toVersion: string
  ): Promise<SkillVersion> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ version: toVersion }),
    });
  },

  delete: async (skillName: string, version: string): Promise<void> => {
    await fetchApi(
      `/skills/${encodeURIComponent(skillName)}/versions/${encodeURIComponent(version)}`,
      { method: 'DELETE' }
    );
  },
};

// Changelogs API
export const changelogsApi = {
  list: async (
    skillName: string,
    params?: { offset?: number; limit?: number }
  ): Promise<{ changelogs: SkillChangelog[]; total: number }> => {
    const searchParams = new URLSearchParams();
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    return fetchApi(
      `/skills/${encodeURIComponent(skillName)}/changelog${query ? `?${query}` : ''}`
    );
  },
};

// Export/Import API
export const transferApi = {
  exportSkill: async (skillName: string): Promise<Blob> => {
    const response = await fetch(
      `${API_BASE}/skills/${encodeURIComponent(skillName)}/export`
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Export failed');
    }
    return response.blob();
  },

  importSkill: async (file: File): Promise<Skill> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/import`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Import failed'
      );
    }

    return response.json();
  },

  importFromGitHub: async (params: {
    url: string;
    checkOnly?: boolean;
    conflictAction?: string;
  }): Promise<{
    success: boolean;
    skill_name: string;
    version: string;
    message: string;
    conflict?: boolean;
    existing_skill?: string;
    existing_version?: string;
  }> => {
    const body: Record<string, unknown> = { url: params.url };
    if (params.checkOnly !== undefined) body.check_only = params.checkOnly;
    if (params.conflictAction) body.conflict_action = params.conflictAction;

    const response = await fetch(`${API_BASE}/import-github`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const detail = error.detail;
      // Handle structured error from 409 conflict
      if (typeof detail === 'object' && detail.message) {
        throw new ApiError(response.status, detail.message);
      }
      throw new ApiError(
        response.status,
        detail || error.message || 'GitHub import failed'
      );
    }

    return response.json();
  },
};

// Filesystem Skills API (from original skills endpoint, not registry)
// These are the skills that the Agent can actually use
export interface FilesystemSkill {
  name: string;
  description: string;
  location: string;
  path: string;
}

export interface FilesystemSkillsResponse {
  skills: FilesystemSkill[];
  total: number;
}

export interface SkillResources {
  scripts: string[];
  references: string[];
  assets: string[];
  other: string[];  // Files in other directories (e.g., rules/, etc.)
}

export interface SkillWithResources {
  name: string;
  description: string;
  content: string;
  base_dir: string;
  resources: SkillResources;
}

// Filesystem Skills API - uses backend URL directly to work in Docker
const SKILLS_API_BASE = BACKEND_API_BASE;

export const filesystemSkillsApi = {
  list: async (): Promise<FilesystemSkillsResponse> => {
    const response = await fetch(`${SKILLS_API_BASE}/skills/`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch skills');
    }
    return response.json();
  },

  get: async (skillName: string): Promise<SkillWithResources> => {
    const response = await fetch(`${SKILLS_API_BASE}/skills/${encodeURIComponent(skillName)}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch skill resources');
    }
    return response.json();
  },

  getFileContent: async (skillName: string, resourceType: string, filename: string): Promise<string> => {
    const response = await fetch(
      `${SKILLS_API_BASE}/skills/${encodeURIComponent(skillName)}/resources/${encodeURIComponent(resourceType)}/${encodeURIComponent(filename)}`
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch file content');
    }
    return response.text();
  },
};

// Keep resourcesApi as alias for backward compatibility
export const resourcesApi = filesystemSkillsApi;

// Files API
export interface UploadedFile {
  file_id: string;
  filename: string;
  path: string;
  size: number;
  content_type: string;
  uploaded_at: string;
}

const FILES_API_BASE = BACKEND_API_BASE;

export const filesApi = {
  upload: async (file: File): Promise<UploadedFile> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${FILES_API_BASE}/files/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'File upload failed'
      );
    }

    return response.json();
  },

  delete: async (fileId: string): Promise<void> => {
    const response = await fetch(`${FILES_API_BASE}/files/${encodeURIComponent(fileId)}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to delete file');
    }
  },
};

// Agent API
export interface AgentUploadedFile {
  file_id: string;
  filename: string;
  path: string;
  content_type: string;
}

export interface AgentRequest {
  request: string;
  session_id: string;  // Session ID for server-side session management
  agent_id?: string;  // Agent preset ID. When set, uses preset config and ignores individual config fields.
  model_provider?: string;  // LLM provider: anthropic, openrouter, openai, google
  model_name?: string;  // Model name/ID for the provider
  skills?: string[];  // Optional list of skills to activate (undefined = all)
  allowed_tools?: string[];  // Optional list of tools to enable (undefined = all)
  max_turns?: number;
  uploaded_files?: AgentUploadedFile[];  // Uploaded files available to the agent
  equipped_mcp_servers?: string[];  // Optional list of MCP servers to enable (undefined = all)
  system_prompt?: string;  // Custom system prompt to append to base prompt
  executor_name?: string;  // Executor name for code execution (custom mode only)
}

export interface StepInfo {
  role: string;
  content: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
}

export interface AgentResponse {
  success: boolean;
  answer: string;
  total_turns: number;
  steps: StepInfo[];
  error?: string;
  trace_id?: string;  // ID of saved trace for later reference
}

// Agent API - calls backend directly to avoid Next.js proxy timeout
const AGENT_API_BASE = BACKEND_API_BASE;

// Stream event types
export interface StreamEvent {
  event_type: 'run_started' | 'turn_start' | 'text_delta' | 'assistant' | 'tool_call' | 'tool_result' | 'output_file' | 'complete' | 'error' | 'trace_saved' | 'steering_received' | 'ask_user';
  turn: number;
  // For turn_start
  max_turns?: number;
  // For text_delta
  text?: string;
  // For assistant
  content?: string;
  input_tokens?: number;
  output_tokens?: number;
  // For tool_call
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  // For tool_result
  tool_result?: string;
  // For complete
  success?: boolean;
  answer?: string;
  total_turns?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
  // For error
  error?: string;
  message?: string;
  // For trace_saved / run_started
  trace_id?: string;
  // For run_started (published agent sessions)
  session_id?: string;
  // For output_file
  file_id?: string;
  filename?: string;
  size?: number;
  content_type?: string;
  download_url?: string;
  description?: string;
  // For ask_user
  prompt_id?: string;
  question?: string;
  options?: string[];
}

// Output file info for display
export interface OutputFileInfo {
  file_id: string;
  filename: string;
  size: number;
  content_type: string;
  download_url: string;
  description?: string;
}

export const agentApi = {
  run: async (request: AgentRequest): Promise<AgentResponse> => {
    // Call backend directly to avoid Next.js proxy timeout for long-running requests
    const response = await fetch(`${AGENT_API_BASE}/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Agent request failed'
      );
    }

    return response.json();
  },

  runStream: async (
    request: AgentRequest,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(`${AGENT_API_BASE}/agent/run/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Agent stream request failed'
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            // Call onEvent and yield to allow React to re-render
            onEvent(data as StreamEvent);
            // Small delay to allow React to process the state update
            await new Promise(resolve => setTimeout(resolve, 0));
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  steerAgent: async (traceId: string, message: string): Promise<void> => {
    const response = await fetch(
      `${AGENT_API_BASE}/agent/run/stream/${encodeURIComponent(traceId)}/steer`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Steer failed: ${response.statusText}`);
    }
  },

  getSession: async (sessionId: string): Promise<SessionMessages> => {
    const response = await fetch(
      `${AGENT_API_BASE}/published/sessions/${encodeURIComponent(sessionId)}/detail`
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Session not found');
    }
    return response.json();
  },

  getSessionTraceIds: async (sessionId: string): Promise<string[]> => {
    const response = await fetch(
      `${AGENT_API_BASE}/traces/by-session/${encodeURIComponent(sessionId)}`
    );
    if (!response.ok) {
      return [];
    }
    const data = await response.json();
    return data.trace_ids || [];
  },
};

// Traces API
export interface TraceListItem {
  id: string;
  request: string;
  skills_used: string[] | null;
  model: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  success: boolean;
  total_turns: number;
  total_input_tokens: number;
  total_output_tokens: number;
  created_at: string;
  duration_ms: number | null;
}

export interface TraceDetail {
  id: string;
  request: string;
  skills_used: string[] | null;
  model: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  success: boolean;
  answer: string | null;
  error: string | null;
  total_turns: number;
  total_input_tokens: number;
  total_output_tokens: number;
  steps: StepInfo[] | null;
  llm_calls: Record<string, unknown>[] | null;
  created_at: string;
  duration_ms: number | null;
}

export interface TraceListResponse {
  traces: TraceListItem[];
  total: number;
  offset: number;
  limit: number;
}

// Traces API uses /api/v1/traces (not under /registry)
// Uses backend URL directly to work in Docker
const TRACES_API_BASE = BACKEND_API_BASE;

export const tracesApi = {
  list: async (params?: {
    success?: boolean;
    skill_name?: string;
    offset?: number;
    limit?: number;
  }): Promise<TraceListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.success !== undefined) searchParams.set('success', String(params.success));
    if (params?.skill_name) searchParams.set('skill_name', params.skill_name);
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));

    const query = searchParams.toString();
    const response = await fetch(`${TRACES_API_BASE}/traces${query ? `?${query}` : ''}`);
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.json();
  },

  get: async (traceId: string): Promise<TraceDetail> => {
    const response = await fetch(`${TRACES_API_BASE}/traces/${encodeURIComponent(traceId)}`);
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.json();
  },

  delete: async (traceId: string): Promise<void> => {
    const response = await fetch(`${TRACES_API_BASE}/traces/${encodeURIComponent(traceId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
  },

  // Export single trace - returns download URL
  exportOne: (traceId: string): string => {
    return `${TRACES_API_BASE}/traces/${encodeURIComponent(traceId)}/export`;
  },

  // Export multiple traces
  exportMany: async (params: {
    trace_ids?: string[];
    skill_name?: string;
    success?: boolean;
    limit?: number;
  }): Promise<Blob> => {
    const response = await fetch(`${TRACES_API_BASE}/traces/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
    });
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.blob();
  },
};

// Tools API - uses backend URL directly to work in Docker
const TOOLS_API_BASE = BACKEND_API_BASE;

export const toolsApi = {
  list: async (category?: string): Promise<ToolListResponse> => {
    const params = category ? `?category=${encodeURIComponent(category)}` : '';
    const response = await fetch(`${TOOLS_API_BASE}/tools/registry${params}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch tools');
    }
    return response.json();
  },

  get: async (toolId: string): Promise<Tool> => {
    const response = await fetch(`${TOOLS_API_BASE}/tools/registry/${encodeURIComponent(toolId)}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch tool');
    }
    return response.json();
  },
};

// MCP Servers API
export interface MCPToolInfo {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface SecretStatus {
  configured: boolean;
  source: 'env' | 'secrets' | 'none';
}

export interface MCPServerInfo {
  name: string;
  display_name: string;
  description: string;
  default_enabled: boolean;
  tools: MCPToolInfo[];
  required_env_vars: string[];
  secrets_status: Record<string, SecretStatus>;
}

export interface MCPServersListResponse {
  servers: MCPServerInfo[];
  count: number;
}

const MCP_API_BASE = BACKEND_API_BASE;

export interface MCPServerCreateRequest {
  name: string;
  display_name: string;
  description: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  default_enabled: boolean;
  tools: Array<{
    name: string;
    description: string;
    inputSchema: Record<string, unknown>;
  }>;
}

export const mcpApi = {
  listServers: async (): Promise<MCPServersListResponse> => {
    const response = await fetch(`${MCP_API_BASE}/mcp/servers`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch MCP servers');
    }
    return response.json();
  },

  getServer: async (name: string): Promise<MCPServerInfo> => {
    const response = await fetch(`${MCP_API_BASE}/mcp/servers/${encodeURIComponent(name)}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch MCP server');
    }
    return response.json();
  },

  createServer: async (request: MCPServerCreateRequest): Promise<MCPServerInfo> => {
    const response = await fetch(`${MCP_API_BASE}/mcp/servers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to create MCP server');
    }
    return response.json();
  },

  deleteServer: async (name: string): Promise<void> => {
    const response = await fetch(`${MCP_API_BASE}/mcp/servers/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to delete MCP server');
    }
  },

  // Tool discovery
  discoverTools: async (name: string): Promise<{
    success: boolean;
    server_name: string;
    tools: Array<{ name: string; description: string; inputSchema: Record<string, unknown> }>;
    tools_count: number;
    error?: string;
  }> => {
    const response = await fetch(
      `${MCP_API_BASE}/mcp/servers/${encodeURIComponent(name)}/discover-tools`,
      { method: 'POST' }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to discover tools');
    }
    return response.json();
  },

  // Secrets management
  setSecret: async (serverName: string, keyName: string, value: string): Promise<{ message: string; source: string }> => {
    const response = await fetch(
      `${MCP_API_BASE}/mcp/servers/${encodeURIComponent(serverName)}/secrets/${encodeURIComponent(keyName)}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to set secret');
    }
    return response.json();
  },

  deleteSecret: async (serverName: string, keyName: string): Promise<void> => {
    const response = await fetch(
      `${MCP_API_BASE}/mcp/servers/${encodeURIComponent(serverName)}/secrets/${encodeURIComponent(keyName)}`,
      {
        method: 'DELETE',
      }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to delete secret');
    }
  },
};

// Agents API
export interface AgentPreset {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  skill_ids: string[] | null;
  mcp_servers: string[] | null;
  builtin_tools: string[] | null;
  max_turns: number;
  model_provider: string | null;
  model_name: string | null;
  executor_name: string | null;
  is_system: boolean;
  is_published: boolean;
  api_response_mode: 'streaming' | 'non_streaming' | null;
  created_at: string;
  updated_at: string;
}

export interface AgentPresetListResponse {
  presets: AgentPreset[];
  total: number;
}

export interface AgentPresetCreateRequest {
  name: string;
  description?: string;
  system_prompt?: string;
  skill_ids?: string[];
  mcp_servers?: string[];
  builtin_tools?: string[];
  max_turns?: number;
  model_provider?: string;
  model_name?: string;
  executor_name?: string;
}

export interface AgentPresetUpdateRequest {
  name?: string;
  description?: string;
  system_prompt?: string;
  skill_ids?: string[];
  mcp_servers?: string[];
  builtin_tools?: string[] | null;
  max_turns?: number;
  model_provider?: string | null;
  model_name?: string | null;
  executor_name?: string | null;
  is_published?: boolean;
}

const AGENTS_API_BASE = BACKEND_API_BASE;

export const agentPresetsApi = {
  list: async (params?: { is_system?: boolean }): Promise<AgentPresetListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.is_system !== undefined) {
      searchParams.set('is_system', String(params.is_system));
    }
    const query = searchParams.toString();
    const response = await fetch(`${AGENTS_API_BASE}/agents${query ? `?${query}` : ''}`);
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.json();
  },

  get: async (id: string): Promise<AgentPreset> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents/${encodeURIComponent(id)}`);
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.json();
  },

  getByName: async (name: string): Promise<AgentPreset> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents/by-name/${encodeURIComponent(name)}`);
    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }
    return response.json();
  },

  create: async (data: AgentPresetCreateRequest): Promise<AgentPreset> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to create agent');
    }
    return response.json();
  },

  update: async (id: string, data: AgentPresetUpdateRequest): Promise<AgentPreset> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to update agent');
    }
    return response.json();
  },

  delete: async (id: string): Promise<void> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to delete agent');
    }
  },

  publish: async (
    id: string,
    data: { api_response_mode: 'streaming' | 'non_streaming' }
  ): Promise<AgentPreset> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents/${encodeURIComponent(id)}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to publish agent');
    }
    return response.json();
  },

  unpublish: async (id: string): Promise<AgentPreset> => {
    const response = await fetch(`${AGENTS_API_BASE}/agents/${encodeURIComponent(id)}/unpublish`, {
      method: 'POST',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to unpublish agent');
    }
    return response.json();
  },
};

// Published Agent API - public endpoints
export interface PublishedAgentInfo {
  id: string;
  name: string;
  description: string | null;
  api_response_mode: 'streaming' | 'non_streaming' | null;
}

export interface PublishedChatRequest {
  request: string;
  session_id?: string;
  uploaded_files?: AgentUploadedFile[];
}

export interface SessionMessages {
  session_id: string;
  agent_id: string;
  messages: Array<{ role: string; content: string | Array<Record<string, unknown>> }>;
  created_at: string;
  updated_at: string;
}

export interface SessionListItem {
  id: string;
  agent_id: string;
  agent_name: string | null;
  message_count: number;
  first_user_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionListItem[];
  total: number;
  offset: number;
  limit: number;
}

const PUBLISHED_API_BASE = BACKEND_API_BASE;

export const publishedAgentApi = {
  getInfo: async (agentId: string): Promise<PublishedAgentInfo> => {
    const response = await fetch(`${PUBLISHED_API_BASE}/published/${encodeURIComponent(agentId)}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Published agent not found');
    }
    return response.json();
  },

  getSession: async (agentId: string, sessionId: string): Promise<SessionMessages> => {
    const response = await fetch(
      `${PUBLISHED_API_BASE}/published/${encodeURIComponent(agentId)}/sessions/${encodeURIComponent(sessionId)}`
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Session not found');
    }
    return response.json();
  },

  chatStream: async (
    agentId: string,
    request: PublishedChatRequest,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(`${PUBLISHED_API_BASE}/published/${encodeURIComponent(agentId)}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Published agent chat failed'
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data as StreamEvent);
            await new Promise(resolve => setTimeout(resolve, 0));
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  steerAgent: async (agentId: string, traceId: string, message: string): Promise<void> => {
    const response = await fetch(
      `${PUBLISHED_API_BASE}/published/${encodeURIComponent(agentId)}/chat/${encodeURIComponent(traceId)}/steer`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Steer failed: ${response.statusText}`);
    }
  },

  listAllSessions: async (params?: {
    agent_id?: string;
    offset?: number;
    limit?: number;
  }): Promise<SessionListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.agent_id) searchParams.set('agent_id', params.agent_id);
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
    const query = searchParams.toString();
    const response = await fetch(`${PUBLISHED_API_BASE}/published/sessions/list${query ? `?${query}` : ''}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch sessions');
    }
    return response.json();
  },

  getSessionDetail: async (sessionId: string): Promise<SessionMessages> => {
    const response = await fetch(
      `${PUBLISHED_API_BASE}/published/sessions/${encodeURIComponent(sessionId)}/detail`
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Session not found');
    }
    return response.json();
  },

  deleteSession: async (sessionId: string): Promise<void> => {
    const response = await fetch(
      `${PUBLISHED_API_BASE}/published/sessions/${encodeURIComponent(sessionId)}`,
      { method: 'DELETE' }
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to delete session');
    }
  },

  deleteAgentSessions: async (agentId: string): Promise<{ deleted_count: number }> => {
    const response = await fetch(
      `${PUBLISHED_API_BASE}/published/${encodeURIComponent(agentId)}/sessions`,
      { method: 'DELETE' }
    );
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to delete sessions');
    }
    return response.json();
  },

  chatSync: async (
    agentId: string,
    request: PublishedChatRequest
  ): Promise<{
    success: boolean;
    answer: string;
    total_turns: number;
    steps: Array<{ role: string; content: string; tool_name?: string; tool_input?: unknown }>;
    error?: string;
    trace_id?: string;
    session_id?: string;
  }> => {
    const response = await fetch(`${PUBLISHED_API_BASE}/published/${encodeURIComponent(agentId)}/chat/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Published agent chat failed'
      );
    }

    return response.json();
  },
};

// Skill Environment Config API
export interface SkillEnvVar {
  name: string;
  description: string;
  secret: boolean;
  default?: string;
}

export interface SkillConfigResponse {
  skill_name: string;
  required_env: SkillEnvVar[];
}

export interface SkillSecretStatus {
  configured: boolean;
  source: 'secrets' | 'env' | 'default' | 'none';
  secret: boolean;
  description: string;
}

export interface SkillSecretsStatusResponse {
  skill_name: string;
  ready: boolean;
  missing: string[];
  status: Record<string, SkillSecretStatus>;
}

export const skillConfigApi = {
  listConfigs: async (): Promise<{ skills: Record<string, { required_env: SkillEnvVar[] }> }> => {
    return fetchApi('/skill-configs');
  },

  getConfig: async (skillName: string): Promise<SkillConfigResponse> => {
    return fetchApi(`/skill-configs/${encodeURIComponent(skillName)}`);
  },

  setConfig: async (skillName: string, requiredEnv: SkillEnvVar[]): Promise<SkillConfigResponse> => {
    return fetchApi(`/skill-configs/${encodeURIComponent(skillName)}`, {
      method: 'PUT',
      body: JSON.stringify({ required_env: requiredEnv }),
    });
  },

  deleteConfig: async (skillName: string): Promise<void> => {
    return fetchApi(`/skill-configs/${encodeURIComponent(skillName)}`, {
      method: 'DELETE',
    });
  },

  getSecretsStatus: async (skillName: string): Promise<SkillSecretsStatusResponse> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/secrets`);
  },

  setSecret: async (skillName: string, keyName: string, value: string): Promise<{ message: string; source: string }> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/secrets/${encodeURIComponent(keyName)}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    });
  },

  deleteSecret: async (skillName: string, keyName: string): Promise<{ message: string }> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/secrets/${encodeURIComponent(keyName)}`, {
      method: 'DELETE',
    });
  },
};

// Skill Dependencies API
export interface DependenciesStatus {
  skill_name: string;
  has_setup_script: boolean;
  setup_script_path: string | null;
  last_installed_at: string | null;
  last_install_success: boolean | null;
  needs_install: boolean;
}

export interface InstallDependenciesTaskResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface InstallTaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  skill_name?: string;
  error?: string;
}

// Install stream event types
export interface InstallStreamEvent {
  event: 'start' | 'log' | 'complete' | 'error';
  skill_name?: string;
  line?: string;
  success?: boolean;
  return_code?: number;
  message?: string;
}

export const skillDependenciesApi = {
  getStatus: async (skillName: string): Promise<DependenciesStatus> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/dependencies`);
  },

  install: async (skillName: string): Promise<InstallDependenciesTaskResponse> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/install-dependencies`, {
      method: 'POST',
    });
  },

  installStream: async (
    skillName: string,
    onEvent: (event: InstallStreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const response = await fetch(`${API_BASE}/skills/${encodeURIComponent(skillName)}/install-dependencies/stream`, {
      method: 'POST',
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(
        response.status,
        error.detail || error.message || 'Installation failed'
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent(data as InstallStreamEvent);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  getInstallTaskStatus: async (taskId: string): Promise<InstallTaskStatus> => {
    return fetchApi(`/tasks/${encodeURIComponent(taskId)}`);
  },

  getInstallLog: async (skillName: string): Promise<{ skill_name: string; install_log: string }> => {
    return fetchApi(`/skills/${encodeURIComponent(skillName)}/dependencies/log`);
  },
};

// File Browser API
export interface BrowserFileEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size: number | null;
  modified_at: string;
  extension: string | null;
  is_text: boolean;
  is_image: boolean;
}

export interface BrowserDirectoryContents {
  path: string;
  parent_path: string | null;
  entries: BrowserFileEntry[];
  breadcrumbs: Array<{ name: string; path: string }>;
}

export interface BrowserFilePreview {
  type: 'text' | 'image';
  content: string;
  extension?: string | null;
  mime_type?: string;
}

const BROWSER_API_BASE = BACKEND_API_BASE;

export const browserApi = {
  listDirectory: async (path: string = ''): Promise<BrowserDirectoryContents> => {
    const params = path ? `?path=${encodeURIComponent(path)}` : '';
    const response = await fetch(`${BROWSER_API_BASE}/browser/list${params}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to list directory');
    }
    return response.json();
  },

  previewFile: async (path: string): Promise<BrowserFilePreview> => {
    const response = await fetch(`${BROWSER_API_BASE}/browser/preview?path=${encodeURIComponent(path)}`);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to preview file');
    }
    return response.json();
  },

  getDownloadUrl: (path: string): string => {
    return `${BROWSER_API_BASE}/browser/download?path=${encodeURIComponent(path)}`;
  },

  getDownloadZipUrl: (path: string): string => {
    return `${BROWSER_API_BASE}/browser/download-zip?path=${encodeURIComponent(path)}`;
  },

  uploadFile: async (targetPath: string, file: File): Promise<BrowserFileEntry> => {
    const formData = new FormData();
    formData.append('file', file);

    const params = targetPath ? `?path=${encodeURIComponent(targetPath)}` : '';
    const response = await fetch(`${BROWSER_API_BASE}/browser/upload${params}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to upload file');
    }

    return response.json();
  },

  deleteFile: async (path: string): Promise<void> => {
    const response = await fetch(`${BROWSER_API_BASE}/browser/delete?path=${encodeURIComponent(path)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to delete file');
    }
  },
};

// Models API
export interface ModelInfo {
  key: string;  // Full key: "provider/model"
  provider: string;
  model_id: string;
  display_name: string;
  context_limit: number;
  supports_tools: boolean;
  supports_vision: boolean;
}

export interface ProviderInfo {
  name: string;
  api_key_set: boolean;
  models: ModelInfo[];
}

export interface ModelsListResponse {
  models: ModelInfo[];
  total: number;
}

export interface ProvidersListResponse {
  providers: ProviderInfo[];
}

const MODELS_API_BASE = BACKEND_API_BASE;

export const modelsApi = {
  list: async (provider?: string): Promise<ModelsListResponse> => {
    const params = provider ? `?provider=${encodeURIComponent(provider)}` : '';
    const response = await fetch(`${MODELS_API_BASE}/models${params}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch models');
    }
    return response.json();
  },

  listProviders: async (): Promise<ProvidersListResponse> => {
    const response = await fetch(`${MODELS_API_BASE}/models/providers`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch providers');
    }
    return response.json();
  },
};

// Executors API
export interface Executor {
  id: string;
  name: string;
  description: string | null;
  image: string;
  port: number;
  memory_limit: string | null;
  cpu_limit: number | null;
  gpu_required: boolean;
  is_builtin: boolean;
  status: 'online' | 'offline';
  created_at: string;
  updated_at: string;
}

export interface ExecutorListResponse {
  executors: Executor[];
  total: number;
}

export interface ExecutorHealthResponse {
  healthy: boolean;
  executor?: string;
  python_version?: string;
  package_count?: number;
  error?: string;
}

const EXECUTORS_API_BASE = BACKEND_API_BASE;

export const executorsApi = {
  list: async (): Promise<ExecutorListResponse> => {
    const response = await fetch(`${EXECUTORS_API_BASE}/executors`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to fetch executors');
    }
    return response.json();
  },

  get: async (name: string): Promise<Executor> => {
    const response = await fetch(`${EXECUTORS_API_BASE}/executors/${encodeURIComponent(name)}`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Executor not found');
    }
    return response.json();
  },

  health: async (name: string): Promise<ExecutorHealthResponse> => {
    const response = await fetch(`${EXECUTORS_API_BASE}/executors/${encodeURIComponent(name)}/health`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Health check failed');
    }
    return response.json();
  },
};

// Backup API
export interface BackupStats {
  skills: number;
  skill_versions: number;
  skill_files: number;
  skill_tests: number;
  skill_changelogs: number;
  agent_presets: number;
  agent_traces: number;
  published_sessions: number;
}

export interface BackupListItem {
  filename: string;
  size_bytes: number;
  created_at: string;
  backup_version: string | null;
  stats: BackupStats | null;
}

export interface BackupListResponse {
  backups: BackupListItem[];
  total: number;
}

export interface RestoreResponse {
  success: boolean;
  message: string;
  snapshot_filename: string | null;
  restored: BackupStats;
  errors: string[];
}

const BACKUP_API_BASE = BACKEND_API_BASE;

export const backupApi = {
  create: async (params?: { includeEnv?: boolean }): Promise<Blob> => {
    const includeEnv = params?.includeEnv !== false;
    const response = await fetch(
      `${BACKUP_API_BASE}/backup/create?include_env=${includeEnv}`,
      { method: 'POST' }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to create backup');
    }
    return response.blob();
  },

  list: async (): Promise<BackupListResponse> => {
    const response = await fetch(`${BACKUP_API_BASE}/backup/list`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to list backups');
    }
    return response.json();
  },

  restoreFromUpload: async (file: File): Promise<RestoreResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${BACKUP_API_BASE}/backup/restore`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to restore backup');
    }
    return response.json();
  },

  restoreFromServer: async (filename: string): Promise<RestoreResponse> => {
    const response = await fetch(
      `${BACKUP_API_BASE}/backup/restore/${encodeURIComponent(filename)}`,
      { method: 'POST' }
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to restore backup');
    }
    return response.json();
  },

  getDownloadUrl: (filename: string): string => {
    return `${BACKUP_API_BASE}/backup/download/${encodeURIComponent(filename)}`;
  },
};

// ── Settings / Environment Variables ──

export interface EnvVariable {
  key: string;
  value: string;
  description: string | null;
  sensitive: boolean;
  source: string;
  category: string;
}

export interface EnvConfigResponse {
  variables: EnvVariable[];
  env_file_path: string;
  env_file_exists: boolean;
}

export const settingsApi = {
  getEnv: async (): Promise<EnvConfigResponse> => {
    const response = await fetch(`${BACKEND_API_BASE}/settings/env`);
    if (!response.ok) {
      throw new ApiError(response.status, 'Failed to load environment variables');
    }
    return response.json();
  },

  createEnv: async (key: string, value: string): Promise<void> => {
    const response = await fetch(`${BACKEND_API_BASE}/settings/env`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to create variable');
    }
  },

  updateEnv: async (key: string, value: string): Promise<void> => {
    const response = await fetch(`${BACKEND_API_BASE}/settings/env`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to update variable');
    }
  },

  deleteEnv: async (key: string): Promise<void> => {
    const response = await fetch(`${BACKEND_API_BASE}/settings/env/${encodeURIComponent(key)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Failed to delete variable');
    }
  },
};

export { ApiError };

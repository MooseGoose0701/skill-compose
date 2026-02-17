'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Bot, CheckCircle2, Settings2, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { agentApi, agentPresetsApi, modelsApi, type StreamEvent, type OutputFileInfo } from '@/lib/api';
import { ChatMessageItem } from '@/components/chat/chat-message';
import type { ChatMessage } from '@/stores/chat-store';
import type { StreamEventRecord } from '@/types/stream-events';
import { handleStreamEvent, serializeEventsToText } from '@/lib/stream-utils';

export function AgentBuilderChat() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentBuilderId, setAgentBuilderId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null);

  // Streaming state
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);
  const [currentOutputFiles, setCurrentOutputFiles] = useState<OutputFileInfo[]>([]);
  const [streamingEvents, setStreamingEvents] = useState<StreamEventRecord[]>([]);

  // Configuration
  const [showConfig, setShowConfig] = useState(true);
  const [maxTurns, setMaxTurns] = useState(60);
  const [selectedModelProvider, setSelectedModelProvider] = useState<string | null>('kimi');
  const [selectedModelName, setSelectedModelName] = useState<string | null>('kimi-k2.5');

  // Session ID for server-side session management
  const [sessionId] = useState(() => crypto.randomUUID());

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // For stop functionality
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentRequestMessagesRef = useRef<string[]>([]);

  // Fetch agent-builder preset ID
  useEffect(() => {
    const fetchAgentBuilder = async () => {
      try {
        setLoadError(null);
        const preset = await agentPresetsApi.getByName('agent-builder');
        setAgentBuilderId(preset.id);
      } catch (error) {
        console.error('Failed to fetch agent-builder:', error);
        setLoadError(error instanceof Error ? error.message : 'Failed to load agent-builder preset');
      }
    };
    fetchAgentBuilder();
  }, []);

  // Fetch available models
  const { data: modelsData } = useQuery({
    queryKey: ['models-providers'],
    queryFn: () => modelsApi.listProviders(),
  });

  const modelProviders = modelsData?.providers || [];

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent]);

  // Helper to remove messages by IDs
  const removeMessages = useCallback((ids: string[]) => {
    setMessages(prev => prev.filter(m => !ids.includes(m.id)));
  }, []);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading || !agentBuilderId) return;

    // Create abort controller for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    const now = Date.now();
    const userMessage: ChatMessage = {
      id: `user-${now}`,
      role: 'user',
      content: input.trim(),
      timestamp: now,
    };

    const assistantMessageId = `assistant-${now}`;
    const assistantMessage: ChatMessage = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: now,
      isLoading: true,
    };

    // Track current request messages for potential removal on stop
    currentRequestMessagesRef.current = [userMessage.id, assistantMessageId];

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);
    setStreamingContent('');
    setStreamingMessageId(assistantMessageId);
    setCurrentOutputFiles([]);

    const events: StreamEventRecord[] = [];
    let traceId: string | undefined;

    try {
      await agentApi.runStream(
        {
          request: userMessage.content,
          session_id: sessionId,
          agent_id: agentBuilderId,
          max_turns: maxTurns,
          model_provider: selectedModelProvider || undefined,
          model_name: selectedModelName || undefined,
        },
        (event: StreamEvent) => {
          // Accumulate text_delta into assistant records, or map other events
          handleStreamEvent(event, events);

          switch (event.event_type) {
            case 'run_started':
              traceId = event.trace_id;
              setMessages(prev => prev.map(m =>
                m.id === assistantMessageId
                  ? { ...m, traceId }
                  : m
              ));
              break;
            case 'output_file':
              if (event.file_id && event.filename) {
                const outputFile: OutputFileInfo = {
                  file_id: event.file_id,
                  filename: event.filename,
                  size: event.size || 0,
                  content_type: event.content_type || 'application/octet-stream',
                  download_url: event.download_url || '',
                  description: event.description,
                };
                setCurrentOutputFiles(prev => [...prev, outputFile]);
              }
              break;
            case 'complete':
              // Check if an agent was created
              const agentIdMatch = event.answer?.match(/Agent.*?ID[:\s]+([a-f0-9-]{36})/i);
              if (agentIdMatch) {
                setCreatedAgentId(agentIdMatch[1]);
              }
              break;
          }

          setStreamingEvents([...events]);
          setStreamingContent(serializeEventsToText(events));
        },
        abortController.signal
      );

      // Mark as complete
      setMessages(prev => prev.map(m =>
        m.id === assistantMessageId
          ? {
              ...m,
              content: serializeEventsToText(events),
              streamEvents: events,
              isLoading: false,
              traceId,
              outputFiles: currentOutputFiles,
            }
          : m
      ));
    } catch (error) {
      // Check if this was an abort (user clicked stop)
      if (error instanceof Error && error.name === 'AbortError') {
        // Request was stopped by user - messages already removed by handleStop
        return;
      }
      const errMsg = error instanceof Error ? error.message : 'Unknown error';
      setMessages(prev => prev.map(m =>
        m.id === assistantMessageId
          ? {
              ...m,
              content: serializeEventsToText(events),
              streamEvents: events,
              isLoading: false,
              error: errMsg,
              traceId,
            }
          : m
      ));
    } finally {
      setIsLoading(false);
      setStreamingContent(null);
      setStreamingMessageId(null);
      setStreamingEvents([]);
      setCurrentOutputFiles([]);
      abortControllerRef.current = null;
      currentRequestMessagesRef.current = [];
    }
  };

  const handleStop = () => {
    if (!isLoading || !abortControllerRef.current) return;

    // Abort the fetch request
    abortControllerRef.current.abort();

    // Remove the messages from this request (user message + loading message)
    if (currentRequestMessagesRef.current.length > 0) {
      removeMessages(currentRequestMessagesRef.current);
    }

    // Reset state
    setIsLoading(false);
    setStreamingMessageId(null);
    setStreamingContent(null);
    setCurrentOutputFiles([]);
    abortControllerRef.current = null;
    currentRequestMessagesRef.current = [];
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  if (loadError) {
    return (
      <Card className="p-8 text-center">
        <div className="h-8 w-8 mx-auto mb-4 text-destructive">✕</div>
        <p className="text-destructive font-medium">Failed to load agent-builder</p>
        <p className="text-xs text-muted-foreground mt-2">{loadError}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() => window.location.reload()}
        >
          Retry
        </Button>
      </Card>
    );
  }

  if (!agentBuilderId) {
    return (
      <Card className="p-8 text-center">
        <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-muted-foreground" />
        <p className="text-muted-foreground">Loading agent-builder...</p>
        <p className="text-xs text-muted-foreground mt-2">
          Make sure the &quot;agent-builder&quot; Agent exists
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col h-[700px]">
      {/* Configuration Toggle */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Bot className="h-4 w-4" />
          <span>Agent Builder</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowConfig(!showConfig)}
          className="gap-1"
        >
          <Settings2 className="h-4 w-4" />
          {showConfig ? 'Hide Config' : 'Config'}
        </Button>
      </div>

      {/* Configuration Panel */}
      {showConfig && (
        <div className="px-4 py-3 border-b bg-muted/20 space-y-3">
          <div className="grid grid-cols-2 gap-4">
            {/* Model Selection */}
            <div className="space-y-1">
              <Label htmlFor="model" className="text-xs">Model</Label>
              <select
                id="model"
                value={selectedModelProvider && selectedModelName ? `${selectedModelProvider}/${selectedModelName}` : ''}
                onChange={(e) => {
                  const value = e.target.value;
                  if (!value) {
                    setSelectedModelProvider(null);
                    setSelectedModelName(null);
                  } else {
                    const [provider, ...modelParts] = value.split('/');
                    setSelectedModelProvider(provider);
                    setSelectedModelName(modelParts.join('/'));
                  }
                }}
                className="w-full h-9 px-3 rounded-md border bg-background text-sm"
              >
                <option value="">Default (Kimi 2.5)</option>
                {modelProviders.map((provider) => (
                  <optgroup key={provider.name} label={provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}>
                    {provider.models.map((model) => (
                      <option key={model.key} value={model.key}>
                        {model.display_name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            {/* Max Turns */}
            <div className="space-y-1">
              <Label htmlFor="max-turns" className="text-xs">Max Turns</Label>
              <Input
                id="max-turns"
                type="number"
                min={1}
                max={60000}
                value={maxTurns}
                onChange={(e) => setMaxTurns(parseInt(e.target.value) || 60)}
                className="h-9"
              />
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="font-medium">Describe the Agent you want to create</p>
            <p className="text-sm mt-2">
              For example: &quot;I need an agent that can analyze CSV files and generate reports&quot;
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessageItem
              key={message.id}
              message={message}
              streamingContent={streamingMessageId === message.id ? streamingContent : undefined}
              streamingEvents={streamingMessageId === message.id ? streamingEvents : undefined}
              streamingOutputFiles={streamingMessageId === message.id ? currentOutputFiles : undefined}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Created Agent Banner */}
      {createdAgentId && (
        <div className="bg-green-50 dark:bg-green-950/30 border-t border-green-200 dark:border-green-800 p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <span className="text-sm font-medium text-green-700 dark:text-green-400">
              Agent created successfully!
            </span>
          </div>
          <Button
            size="sm"
            onClick={() => router.push(`/agents/${createdAgentId}`)}
          >
            View Agent
          </Button>
        </div>
      )}

      {/* Input Area */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe your agent requirements..."
            className="min-h-[80px] resize-none"
            disabled={isLoading}
          />
        </div>
        <div className="flex justify-between items-center mt-2">
          <span className="text-xs text-muted-foreground">
            Enter to send
          </span>
          {isLoading ? (
            <Button onClick={handleStop} variant="destructive">
              <Square className="h-4 w-4 mr-1" />
              Stop
            </Button>
          ) : (
            <Button onClick={() => handleSubmit()} disabled={!input.trim()}>
              Send
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Shared utilities for converting raw session messages (Anthropic format)
 * into ChatMessage[] with StreamEventRecords for the chat UI.
 */
import type { ChatMessage } from '@/stores/chat-store';
import type { StreamEventRecord } from '@/types/stream-events';

interface RawMessage {
  role: string;
  content: string | Array<Record<string, unknown>>;
}

export function sessionMessagesToChatMessages(raw: RawMessage[]): ChatMessage[] {
  const result: ChatMessage[] = [];
  let events: StreamEventRecord[] = [];
  let pendingAssistantId: string | null = null;
  let toolIdToName: Record<string, string> = {};
  let eventCounter = 0;

  const nextId = () => `evt-${eventCounter++}`;
  const now = Date.now();

  const flushAssistant = () => {
    if (pendingAssistantId !== null) {
      result.push({
        id: pendingAssistantId,
        role: 'assistant',
        content: '',
        timestamp: now,
        streamEvents: events.length > 0 ? [...events] : undefined,
      });
      events = [];
      toolIdToName = {};
      pendingAssistantId = null;
    }
  };

  for (let i = 0; i < raw.length; i++) {
    const msg = raw[i];

    if (msg.role === 'user') {
      // Check if this is a tool_result message (sent back by the system)
      if (Array.isArray(msg.content)) {
        const hasToolResult = msg.content.some(
          (b) => typeof b === 'object' && b !== null && b.type === 'tool_result'
        );
        if (hasToolResult) {
          for (const block of msg.content) {
            if (typeof block === 'object' && block !== null && block.type === 'tool_result') {
              const toolUseId = typeof block.tool_use_id === 'string' ? block.tool_use_id : '';
              const toolName = toolIdToName[toolUseId] || 'tool';
              const resultContent = typeof block.content === 'string'
                ? block.content
                : JSON.stringify(block.content);
              events.push({
                id: nextId(),
                timestamp: now,
                type: 'tool_result',
                data: {
                  toolName,
                  toolResult: resultContent,
                  success: !block.is_error,
                },
              });

              // Extract output_file events from tool results that detect new files
              if (toolName === 'execute_code' || toolName === 'bash' || toolName === 'write') {
                try {
                  const parsed = JSON.parse(resultContent);
                  if (Array.isArray(parsed.new_files)) {
                    for (const nf of parsed.new_files) {
                      if (nf.download_url) {
                        events.push({
                          id: nextId(),
                          timestamp: now,
                          type: 'output_file',
                          data: {
                            fileId: nf.file_id || nextId(),
                            filename: nf.filename || 'file',
                            size: nf.size || 0,
                            contentType: nf.content_type || 'application/octet-stream',
                            downloadUrl: nf.download_url,
                          },
                        });
                      }
                    }
                  }
                } catch { /* not JSON, skip */ }
              }
            }
          }
          continue;
        }
      }

      // Regular user message — flush any pending assistant first
      flushAssistant();

      let userText = '';
      if (typeof msg.content === 'string') {
        userText = msg.content;
      } else if (Array.isArray(msg.content)) {
        const texts: string[] = [];
        for (const block of msg.content) {
          if (typeof block === 'object' && block !== null && block.type === 'text' && typeof block.text === 'string') {
            texts.push(block.text);
          }
        }
        userText = texts.join('\n');
      }

      result.push({
        id: `msg-${i}`,
        role: 'user',
        content: userText,
        timestamp: now,
      });
      continue;
    }

    if (msg.role === 'assistant') {
      flushAssistant();
      pendingAssistantId = `msg-${i}`;

      if (typeof msg.content === 'string') {
        if (msg.content) {
          events.push({
            id: nextId(),
            timestamp: now,
            type: 'assistant',
            data: { content: msg.content },
          });
        }
      } else if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (typeof block !== 'object' || block === null) continue;

          if (block.type === 'text' && typeof block.text === 'string') {
            if (block.text) {
              events.push({
                id: nextId(),
                timestamp: now,
                type: 'assistant',
                data: { content: block.text },
              });
            }
          } else if (block.type === 'tool_use') {
            const toolName = typeof block.name === 'string' ? block.name : 'tool';
            const toolId = typeof block.id === 'string' ? block.id : '';
            if (toolId) toolIdToName[toolId] = toolName;

            events.push({
              id: nextId(),
              timestamp: now,
              type: 'tool_call',
              data: {
                toolName,
                toolInput: (typeof block.input === 'object' && block.input !== null)
                  ? block.input as Record<string, unknown>
                  : undefined,
              },
            });
          }
        }
      }
      continue;
    }
  }

  flushAssistant();
  return result;
}

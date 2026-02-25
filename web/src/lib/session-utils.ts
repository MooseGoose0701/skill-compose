/**
 * Shared utilities for converting raw session messages into ChatMessage[].
 *
 * Session `messages` column now stores ChatMessage-format dicts directly
 * (with streamEvents and attachedFiles), so this is a simple pass-through
 * that hydrates id/timestamp fields.
 */
import type { ChatMessage } from '@/stores/chat-store';

interface RawMessage {
  role: string;
  content: string | Array<Record<string, unknown>>;
  streamEvents?: Array<Record<string, unknown>>;
  attachedFiles?: Array<{ file_id: string; filename: string }>;
}

export function sessionMessagesToChatMessages(raw: RawMessage[]): ChatMessage[] {
  const now = Date.now();
  let eventCounter = 0;

  return raw.map((msg, i) => {
    const streamEvents = msg.streamEvents;
    // Regenerate id/timestamp on each event if present
    const hydratedEvents = streamEvents?.map((evt) => ({
      ...evt,
      id: `evt-${eventCounter++}`,
      timestamp: now,
    }));

    return {
      id: `msg-${i}`,
      role: msg.role as 'user' | 'assistant',
      content: (typeof msg.content === 'string' ? msg.content : '') || '',
      timestamp: now,
      streamEvents: hydratedEvents as ChatMessage['streamEvents'],
      attachedFiles: msg.attachedFiles,
    };
  });
}

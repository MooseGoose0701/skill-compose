'use client';

import { useEffect, useRef } from 'react';
import { agentApi } from '@/lib/api';
import { useChatStore } from '@/stores/chat-store';
import { sessionMessagesToChatMessages } from '@/lib/session-utils';

/**
 * On mount, if the store has a sessionId but no messages,
 * fetch the session from the server and populate the message list.
 */
export function useChatSessionRestore() {
  const sessionId = useChatStore((s) => s.sessionId);
  const messages = useChatStore((s) => s.messages);
  const isRunning = useChatStore((s) => s.isRunning);
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    if (!sessionId || messages.length > 0 || isRunning) return;

    attempted.current = true;

    (async () => {
      try {
        const session = await agentApi.getSession(sessionId);
        if (session && session.messages && session.messages.length > 0) {
          const chatMessages = sessionMessagesToChatMessages(
            session.messages as Array<{ role: string; content: string | Array<Record<string, unknown>> }>
          );
          // Populate store
          const store = useChatStore.getState();
          for (const msg of chatMessages) {
            store.addMessage(msg);
          }
        }
      } catch {
        // 404 or network error — start fresh, no messages to restore
      }
    })();
  }, [sessionId, messages.length, isRunning]);
}

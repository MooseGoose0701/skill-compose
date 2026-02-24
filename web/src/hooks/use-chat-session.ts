'use client';

import { useEffect, useRef } from 'react';
import { agentApi } from '@/lib/api';
import { useChatStore } from '@/stores/chat-store';
import { sessionMessagesToChatMessages } from '@/lib/session-utils';

/**
 * On mount, if the store has a sessionId but no messages,
 * fetch the session from the server and populate the message list.
 * Also fetches trace IDs for the session and attaches them to assistant messages.
 *
 * Uses setMessages() for a single batch state update (instead of N addMessage calls).
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

    const store = useChatStore.getState();
    store.setIsRestoringSession(true);

    (async () => {
      try {
        // Fetch session messages and trace IDs in parallel
        const [session, traceIds] = await Promise.all([
          agentApi.getSession(sessionId),
          agentApi.getSessionTraceIds(sessionId),
        ]);

        if (session && session.messages && session.messages.length > 0) {
          const chatMessages = sessionMessagesToChatMessages(
            session.messages as Array<{ role: string; content: string | Array<Record<string, unknown>> }>
          );

          // Attach trace IDs to assistant messages (chronological order matches)
          if (traceIds.length > 0) {
            let traceIndex = 0;
            for (const msg of chatMessages) {
              if (msg.role === 'assistant' && traceIndex < traceIds.length) {
                msg.traceId = traceIds[traceIndex];
                traceIndex++;
              }
            }
          }

          // Batch update: single state change instead of N addMessage calls
          useChatStore.getState().setMessages(chatMessages);
        }
      } catch {
        // 404 or network error — start fresh, no messages to restore
      } finally {
        useChatStore.getState().setIsRestoringSession(false);
      }
    })();
  }, [sessionId, messages.length, isRunning]);
}

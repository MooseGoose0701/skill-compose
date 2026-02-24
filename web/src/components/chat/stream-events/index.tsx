"use client";

import React from "react";
import type { StreamEventRecord } from "@/types/stream-events";
import { TurnDivider } from "./turn-divider";
import { ThinkingBlock } from "./thinking-block";
import { ToolCallCard } from "./tool-call-card";
import { ToolResultItem } from "./tool-result-item";
import { OutputFileCard } from "./output-file-card";
import { CompleteBanner } from "./complete-banner";
import { ErrorBanner } from "./error-banner";
import { SteeringMessage } from "./steering-message";
import { AskUserCard } from "./ask-user-card";

interface StreamEventsRendererProps {
  events: StreamEventRecord[];
  /** Show all tool inputs/results expanded by default */
  expandAll?: boolean;
  /** When true, the last assistant block uses plain text instead of Markdown for performance */
  isStreaming?: boolean;
  /** Callback when user responds to an ask_user prompt */
  onAskUserRespond?: (promptId: string, answer: string) => void;
}

/**
 * Renders a list of stream events as structured UI components
 */
export const StreamEventsRenderer = React.memo(function StreamEventsRenderer({ events, expandAll = false, isStreaming = false, onAskUserRespond }: StreamEventsRendererProps) {
  // Find the index of the last assistant event for streaming optimization
  let lastAssistantIndex = -1;
  if (isStreaming) {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'assistant') {
        lastAssistantIndex = i;
        break;
      }
    }
  }

  return (
    <div className="space-y-0">
      {events.map((event, index) => {
        switch (event.type) {
          case 'turn_start':
            return <TurnDivider key={event.id} data={event.data} />;

          case 'assistant':
            return <ThinkingBlock key={event.id} data={event.data} isStreaming={isStreaming && index === lastAssistantIndex} />;

          case 'tool_call':
            return <ToolCallCard key={event.id} data={event.data} defaultExpanded={expandAll} />;

          case 'tool_result':
            return <ToolResultItem key={event.id} data={event.data} defaultExpanded={expandAll} />;

          case 'output_file':
            return <OutputFileCard key={event.id} data={event.data} />;

          case 'complete':
            return <CompleteBanner key={event.id} data={event.data} />;

          case 'error':
            return <ErrorBanner key={event.id} data={event.data} />;

          case 'steering_received':
            return <SteeringMessage key={event.id} data={event.data} />;

          case 'ask_user':
            return (
              <AskUserCard
                key={event.id}
                data={event.data}
                onRespond={onAskUserRespond}
              />
            );

          // run_started and trace_saved don't have visible UI
          case 'run_started':
          case 'trace_saved':
            return null;

          default:
            return null;
        }
      })}
    </div>
  );
});

// Re-export individual components for direct usage
export { TurnDivider } from "./turn-divider";
export { ThinkingBlock } from "./thinking-block";
export { ToolCallCard } from "./tool-call-card";
export { ToolResultItem } from "./tool-result-item";
export { OutputFileCard } from "./output-file-card";
export { CompleteBanner } from "./complete-banner";
export { ErrorBanner } from "./error-banner";
export { SteeringMessage } from "./steering-message";
export { AskUserCard } from "./ask-user-card";

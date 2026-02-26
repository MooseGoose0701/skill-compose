/**
 * Utility functions for stream event processing
 */

import type { StreamEvent } from '@/lib/api';
import type {
  StreamEventRecord,
  TurnStartRecord,
  AssistantRecord,
  ToolCallRecord,
  ToolResultRecord,
  OutputFileRecord,
  CompleteRecord,
  ErrorRecord,
  RunStartedRecord,
  TraceSavedRecord,
  SteeringReceivedRecord,
  AskUserRecord,
} from '@/types/stream-events';

let eventIdCounter = 0;

/**
 * Generate a unique ID for a stream event record
 */
function generateEventId(): string {
  return `event-${Date.now()}-${++eventIdCounter}`;
}

/**
 * Convert a StreamEvent from the API to a structured StreamEventRecord
 */
export function mapEventToRecord(event: StreamEvent): StreamEventRecord | null {
  const base = {
    id: generateEventId(),
    timestamp: Date.now(),
  };

  switch (event.event_type) {
    case 'run_started':
      return {
        ...base,
        type: 'run_started',
        data: {
          traceId: event.trace_id,
          sessionId: event.session_id,
        },
      } as RunStartedRecord;

    case 'turn_start':
      return {
        ...base,
        type: 'turn_start',
        data: {
          turn: event.turn,
          maxTurns: event.max_turns || 60,
        },
      } as TurnStartRecord;

    case 'assistant':
      // Only create record if there's actual content
      if (!event.content) return null;
      return {
        ...base,
        type: 'assistant',
        data: {
          content: event.content,
          inputTokens: event.input_tokens,
          outputTokens: event.output_tokens,
        },
      } as AssistantRecord;

    case 'tool_call':
      return {
        ...base,
        type: 'tool_call',
        data: {
          toolName: event.tool_name || 'unknown',
          toolInput: event.tool_input,
        },
      } as ToolCallRecord;

    case 'tool_result':
      return {
        ...base,
        type: 'tool_result',
        data: {
          toolName: event.tool_name || 'unknown',
          toolResult: event.tool_result,
          success: true, // Assume success unless error event follows
        },
      } as ToolResultRecord;

    case 'output_file':
      if (!event.file_id || !event.filename || !event.download_url) return null;
      return {
        ...base,
        type: 'output_file',
        data: {
          fileId: event.file_id,
          filename: event.filename,
          size: event.size || 0,
          contentType: event.content_type || 'application/octet-stream',
          downloadUrl: event.download_url,
          description: event.description,
        },
      } as OutputFileRecord;

    case 'complete':
      return {
        ...base,
        type: 'complete',
        data: {
          success: event.success ?? true,
          answer: event.answer,
          totalTurns: event.total_turns || 0,
          totalInputTokens: event.total_input_tokens,
          totalOutputTokens: event.total_output_tokens,
        },
      } as CompleteRecord;

    case 'error':
      return {
        ...base,
        type: 'error',
        data: {
          message: event.message || event.error || 'Unknown error',
        },
      } as ErrorRecord;

    case 'trace_saved':
      return {
        ...base,
        type: 'trace_saved',
        data: {
          traceId: event.trace_id || '',
        },
      } as TraceSavedRecord;

    case 'steering_received':
      return {
        ...base,
        type: 'steering_received',
        data: {
          message: event.message || '',
        },
      } as SteeringReceivedRecord;

    case 'ask_user':
      if (!event.prompt_id || !event.question) return null;
      return {
        ...base,
        type: 'ask_user',
        data: {
          promptId: event.prompt_id,
          question: event.question,
          options: event.options,
        },
      } as AskUserRecord;

    default:
      return null;
  }
}

/**
 * Handle a stream event by accumulating text_delta events into assistant records.
 * This mutates the events array in place for performance.
 */
export function handleStreamEvent(event: StreamEvent, events: StreamEventRecord[]): void {
  if (event.event_type === 'text_delta' && event.text) {
    // Append to last assistant record, or create a new one
    const last = events[events.length - 1];
    if (last && last.type === 'assistant') {
      (last as AssistantRecord).data.content += event.text;
    } else {
      events.push({
        id: generateEventId(),
        timestamp: Date.now(),
        type: 'assistant',
        data: {
          content: event.text,
        },
      } as AssistantRecord);
    }
  } else if (event.event_type === 'steering_received') {
    // Deduplicate: handleSteer optimistically inserts a local steering_received
    // event before the SSE echo arrives. Skip the SSE echo if a matching
    // optimistic entry already exists.
    const msg = event.message || '';
    const alreadyExists = events.some(
      (e) => e.type === 'steering_received'
        && (e as SteeringReceivedRecord).data.message === msg
    );
    if (!alreadyExists) {
      const record = mapEventToRecord(event);
      if (record) events.push(record);
    }
  } else {
    const record = mapEventToRecord(event);
    if (record) {
      events.push(record);
    }
  }
}

/**
 * Serialize stream events to plain text format (for backward compatibility)
 * This produces output similar to the old string concatenation approach
 */
export function serializeEventsToText(events: StreamEventRecord[]): string {
  let result = '';

  for (const event of events) {
    switch (event.type) {
      case 'turn_start':
        result += `\n━━━ Turn ${event.data.turn}/${event.data.maxTurns} ━━━\n`;
        break;

      case 'assistant':
        result += `\n${event.data.content}\n`;
        break;

      case 'tool_call': {
        result += `\n🔧 Calling: ${event.data.toolName}\n`;
        if (event.data.toolInput && Object.keys(event.data.toolInput).length > 0) {
          const inputStr = JSON.stringify(event.data.toolInput, null, 2);
          if (inputStr.length <= 500) {
            result += `   Input: ${inputStr}\n`;
          } else {
            result += `   Input: ${inputStr.slice(0, 500)}...\n`;
          }
        }
        break;
      }

      case 'tool_result': {
        if (event.data.toolResult) {
          const resultStr = event.data.toolResult;
          if (resultStr.length <= 300) {
            result += `   ✓ ${event.data.toolName} → ${resultStr}\n`;
          } else {
            result += `   ✓ ${event.data.toolName} → ${resultStr.slice(0, 300)}...\n`;
          }
        } else {
          result += `   ✓ ${event.data.toolName} completed\n`;
        }
        break;
      }

      case 'output_file':
        result += `\n📁 Output file: ${event.data.filename}\n`;
        break;

      case 'complete':
        result += `\n━━━ Complete (${event.data.totalTurns} turns) ━━━\n`;
        break;

      case 'error':
        result += `\n❌ Error: ${event.data.message}\n`;
        break;

      case 'steering_received':
        result += `\n🎯 Steering: ${event.data.message}\n`;
        break;

      case 'ask_user':
        result += `\n❓ Question: ${event.data.question}\n`;
        if (event.data.options) {
          result += `   Options: ${event.data.options.join(' | ')}\n`;
        }
        break;

      // run_started and trace_saved don't produce visible text
      case 'run_started':
      case 'trace_saved':
        break;
    }
  }

  return result;
}

/**
 * Reset event ID counter (useful for testing)
 */
export function resetEventIdCounter(): void {
  eventIdCounter = 0;
}

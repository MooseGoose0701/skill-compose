/**
 * Stream Event Types for structured UI rendering
 * These types represent the structured data for each streaming event type
 */

// Base event record that all stream events extend
export interface StreamEventRecordBase {
  id: string;
  timestamp: number;
}

// Turn start event data
export interface TurnStartData {
  turn: number;
  maxTurns: number;
}

export interface TurnStartRecord extends StreamEventRecordBase {
  type: 'turn_start';
  data: TurnStartData;
}

// Assistant thinking/content event data
export interface AssistantData {
  content: string;
  inputTokens?: number;
  outputTokens?: number;
}

export interface AssistantRecord extends StreamEventRecordBase {
  type: 'assistant';
  data: AssistantData;
}

// Tool call event data
export interface ToolCallData {
  toolName: string;
  toolInput?: Record<string, unknown>;
}

export interface ToolCallRecord extends StreamEventRecordBase {
  type: 'tool_call';
  data: ToolCallData;
}

// Tool result event data
export interface ToolResultData {
  toolName: string;
  toolResult?: string;
  success: boolean;
}

export interface ToolResultRecord extends StreamEventRecordBase {
  type: 'tool_result';
  data: ToolResultData;
}

// Output file event data
export interface OutputFileData {
  fileId: string;
  filename: string;
  size: number;
  contentType: string;
  downloadUrl: string;
  description?: string;
}

export interface OutputFileRecord extends StreamEventRecordBase {
  type: 'output_file';
  data: OutputFileData;
}

// Complete event data
export interface CompleteData {
  success: boolean;
  answer?: string;
  totalTurns: number;
  totalInputTokens?: number;
  totalOutputTokens?: number;
}

export interface CompleteRecord extends StreamEventRecordBase {
  type: 'complete';
  data: CompleteData;
}

// Error event data
export interface ErrorData {
  message: string;
}

export interface ErrorRecord extends StreamEventRecordBase {
  type: 'error';
  data: ErrorData;
}

// Run started event data (optional, for trace tracking)
export interface RunStartedData {
  traceId?: string;
  sessionId?: string;
}

export interface RunStartedRecord extends StreamEventRecordBase {
  type: 'run_started';
  data: RunStartedData;
}

// Trace saved event data
export interface TraceSavedData {
  traceId: string;
}

export interface TraceSavedRecord extends StreamEventRecordBase {
  type: 'trace_saved';
  data: TraceSavedData;
}

// Steering received event data
export interface SteeringReceivedData {
  message: string;
}

export interface SteeringReceivedRecord extends StreamEventRecordBase {
  type: 'steering_received';
  data: SteeringReceivedData;
}

// Ask user event data (agent run ends, resumes when user replies)
export interface AskUserData {
  promptId: string;
  question: string;
  options?: string[];
}

export interface AskUserRecord extends StreamEventRecordBase {
  type: 'ask_user';
  data: AskUserData;
}

// Union type of all stream event records
export type StreamEventRecord =
  | TurnStartRecord
  | AssistantRecord
  | ToolCallRecord
  | ToolResultRecord
  | OutputFileRecord
  | CompleteRecord
  | ErrorRecord
  | RunStartedRecord
  | TraceSavedRecord
  | SteeringReceivedRecord
  | AskUserRecord;

// Type guard functions
export function isTurnStartRecord(record: StreamEventRecord): record is TurnStartRecord {
  return record.type === 'turn_start';
}

export function isAssistantRecord(record: StreamEventRecord): record is AssistantRecord {
  return record.type === 'assistant';
}

export function isToolCallRecord(record: StreamEventRecord): record is ToolCallRecord {
  return record.type === 'tool_call';
}

export function isToolResultRecord(record: StreamEventRecord): record is ToolResultRecord {
  return record.type === 'tool_result';
}

export function isOutputFileRecord(record: StreamEventRecord): record is OutputFileRecord {
  return record.type === 'output_file';
}

export function isCompleteRecord(record: StreamEventRecord): record is CompleteRecord {
  return record.type === 'complete';
}

export function isErrorRecord(record: StreamEventRecord): record is ErrorRecord {
  return record.type === 'error';
}

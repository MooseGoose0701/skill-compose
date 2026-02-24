"use client";

import React from "react";
import Link from "next/link";
import { Download, FileText, Paperclip, Copy, Check } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatFileSize } from "@/lib/formatters";
import type { StepInfo, OutputFileInfo } from "@/lib/api";
import type { ChatMessage } from "@/stores/chat-store";
import type { StreamEventRecord } from "@/types/stream-events";
import { StreamEventsRenderer } from "./stream-events";

interface ChatMessageItemProps {
  message: ChatMessage;
  streamingContent?: string | null;
  streamingOutputFiles?: OutputFileInfo[];
  /** Structured stream events for rich UI rendering (used during streaming) */
  streamingEvents?: StreamEventRecord[];
  /** Hide trace link (for published pages where traces aren't accessible) */
  hideTraceLink?: boolean;
  /** Callback when user responds to an ask_user prompt */
  onAskUserRespond?: (promptId: string, answer: string) => void;
}

export const ChatMessageItem = React.memo(function ChatMessageItem({
  message,
  streamingContent,
  streamingOutputFiles,
  streamingEvents,
  hideTraceLink,
  onAskUserRespond,
}: ChatMessageItemProps) {
  const [showSteps, setShowSteps] = React.useState(false);

  const displayContent = streamingContent ?? message.content;
  const isStreaming = streamingContent !== null && streamingContent !== undefined;

  // Use streaming events if available, otherwise fall back to stored events
  const events = streamingEvents || message.streamEvents;
  const hasStructuredEvents = events && events.length > 0;

  const outputFiles = streamingOutputFiles || message.outputFiles || [];

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:62610';

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <Card className="max-w-[85%] p-3 px-4 bg-primary text-primary-foreground">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          {message.attachedFiles && message.attachedFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-primary-foreground/20">
              {message.attachedFiles.map((file) => (
                <span
                  key={file.file_id}
                  className="inline-flex items-center gap-1 text-xs opacity-80 bg-primary-foreground/10 rounded px-1.5 py-0.5"
                >
                  <Paperclip className="h-3 w-3" />
                  <span className="max-w-[150px] truncate">{file.filename}</span>
                </span>
              ))}
            </div>
          )}
        </Card>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <Card className="p-4 w-full">
        {message.isLoading && !displayContent ? (
          <div className="flex items-center gap-2">
            <Spinner size="md" />
            <span className="text-sm text-muted-foreground">Agent is thinking...</span>
          </div>
        ) : (
          <>
            {hasStructuredEvents ? (
              <StreamEventsRenderer events={events} isStreaming={isStreaming} onAskUserRespond={onAskUserRespond} />
            ) : (
              <pre className="text-sm whitespace-pre-wrap font-sans overflow-x-auto">{displayContent}</pre>
            )}
            {/* Only show separate error when NOT using structured events (fallback mode) */}
            {!hasStructuredEvents && message.error && (
              <p className="text-sm text-red-500 mt-2">Error: {message.error}</p>
            )}
            {/* Only show separate Output Files section when NOT using structured events (fallback mode) */}
            {!hasStructuredEvents && outputFiles.length > 0 && (
              <div className="mt-3 pt-3 border-t">
                <div className="text-sm font-medium mb-2 flex items-center gap-1">
                  <FileText className="h-4 w-4" />
                  Output Files
                </div>
                <div className="space-y-2">
                  {outputFiles.map((file) => (
                    <a
                      key={file.file_id}
                      href={`${backendUrl}${file.download_url}`}
                      download={file.filename}
                      className="flex items-center gap-2 p-2 bg-muted rounded hover:bg-muted/80 transition-colors"
                    >
                      <Download className="h-4 w-4 text-primary" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{file.filename}</div>
                        {file.description && (
                          <div className="text-xs text-muted-foreground truncate">{file.description}</div>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatFileSize(file.size)}
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}
            {(message.isLoading || isStreaming) && (
              <div className="flex items-center gap-2 mt-2 pt-2 border-t">
                <Spinner size="sm" />
                <span className="text-xs text-muted-foreground">Running...</span>
              </div>
            )}
            {message.traceId && !hideTraceLink && (
              <TraceIdDisplay traceId={message.traceId} />
            )}
            {(message.steps && message.steps.length > 0) ? (
              <div className="mt-2 flex items-center gap-3">
                <button
                  onClick={() => setShowSteps(!showSteps)}
                  className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  {showSteps ? "Hide" : "Show"} steps ({message.steps.length})
                </button>
              </div>
            ) : null}
            {showSteps && message.steps && (
              <div className="mt-2 space-y-2 max-h-60 overflow-auto">
                {message.steps.map((step, i) => (
                  <StepCard key={i} step={step} index={i} />
                ))}
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
});

export function TraceIdDisplay({ traceId }: { traceId: string }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(traceId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shortId = traceId.length > 12 ? `${traceId.slice(0, 8)}...${traceId.slice(-4)}` : traceId;

  return (
    <div className="mt-3 pt-3 border-t">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">Trace:</span>
        <code className="bg-muted px-1.5 py-0.5 rounded font-mono" title={traceId}>
          {shortId}
        </code>
        <button
          onClick={handleCopy}
          className="text-muted-foreground hover:text-foreground"
          title="Copy trace ID"
        >
          {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
        </button>
        <Link
          href={`/traces/${traceId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline ml-1"
        >
          View ↗
        </Link>
      </div>
    </div>
  );
}

export function StepCard({ step, index }: { step: StepInfo; index: number }) {
  const [expanded, setExpanded] = React.useState(false);

  return (
    <div className="text-xs bg-muted rounded p-2">
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="font-mono text-muted-foreground">{index + 1}.</span>
        {step.tool_name ? (
          <Badge variant="outline" className="text-xs">
            {step.tool_name}
          </Badge>
        ) : (
          <span className="text-muted-foreground">{step.role}</span>
        )}
        <span className="truncate flex-1">{step.content.slice(0, 50)}...</span>
      </div>
      {expanded && (
        <div className="mt-2 space-y-1">
          {step.tool_input && (
            <div>
              <span className="text-muted-foreground">Input:</span>
              <pre className="text-xs bg-background p-1 rounded overflow-auto max-h-32">
                {JSON.stringify(step.tool_input, null, 2)}
              </pre>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">Content:</span>
            <pre className="text-xs bg-background p-1 rounded overflow-auto max-h-32 whitespace-pre-wrap">
              {step.content.slice(0, 500)}
              {step.content.length > 500 && "..."}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

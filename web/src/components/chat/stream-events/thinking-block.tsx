"use client";

import { MessageSquare } from "lucide-react";
import { LazyMarkdown } from "@/components/ui/lazy-markdown";
import type { AssistantData } from "@/types/stream-events";

interface ThinkingBlockProps {
  data: AssistantData;
  /** When true, use plain <pre> to avoid expensive Markdown/SyntaxHighlighter re-renders */
  isStreaming?: boolean;
}

export function ThinkingBlock({ data, isStreaming }: ThinkingBlockProps) {
  return (
    <div className="flex gap-2 py-1.5">
      <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0 mt-1" />
      <div className="flex-1 text-sm text-foreground min-w-0">
        {isStreaming ? (
          <pre className="whitespace-pre-wrap font-sans">{data.content}</pre>
        ) : (
          <LazyMarkdown>{data.content}</LazyMarkdown>
        )}
      </div>
    </div>
  );
}

"use client";

import type { MCPToolInfo } from "@/lib/api";

export function MCPToolCard({ tool }: { tool: MCPToolInfo }) {
  return (
    <div className="p-3 rounded-lg border bg-muted/30">
      <div className="flex items-center gap-2">
        <code className="text-sm font-mono font-medium">{tool.name}</code>
      </div>
      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
        {tool.description}
      </p>
    </div>
  );
}

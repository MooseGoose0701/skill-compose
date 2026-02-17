"use client";

import React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n/client";
import type { MCPToolInfo } from "@/lib/api";
import { MCPToolCard } from "./mcp-tool-card";

const TOOLS_COLLAPSE_THRESHOLD = 3;

interface ToolsListProps {
  tools: MCPToolInfo[];
  hasSecrets: boolean;
}

export function ToolsList({ tools, hasSecrets }: ToolsListProps) {
  const { t } = useTranslation("mcp");
  const [expanded, setExpanded] = React.useState(false);

  const shouldCollapse = tools.length > TOOLS_COLLAPSE_THRESHOLD;
  const visibleTools = shouldCollapse && !expanded ? tools.slice(0, TOOLS_COLLAPSE_THRESHOLD) : tools;
  const hiddenCount = tools.length - TOOLS_COLLAPSE_THRESHOLD;

  return (
    <div className={`space-y-2 ${hasSecrets ? "mt-4 pt-4 border-t" : ""}`}>
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {t("availableToolsCount", { count: tools.length })}
      </p>
      <div className="grid gap-2">
        {visibleTools.map((tool) => (
          <MCPToolCard key={tool.name} tool={tool} />
        ))}
      </div>
      {shouldCollapse && (
        <Button
          variant="ghost"
          size="sm"
          className="w-full text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3 mr-1" />
              {t("showLess")}
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3 mr-1" />
              {t("showMoreTools", { count: hiddenCount })}
            </>
          )}
        </Button>
      )}
    </div>
  );
}

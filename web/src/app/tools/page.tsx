"use client";

import React from "react";
import { useTools } from "@/hooks/use-tools";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Wrench, Terminal, BookOpen, Search, Info, Download } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { useTranslation } from "@/i18n/client";
import type { Tool } from "@/types/skill";

// Category icons
const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  skill_management: <BookOpen className="h-5 w-5" />,
  code_execution: <Terminal className="h-5 w-5" />,
  code_exploration: <Search className="h-5 w-5" />,
  output: <Download className="h-5 w-5" />,
};

function ToolCard({ tool }: { tool: Tool }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-md bg-blue-500/10 text-blue-500">
            {CATEGORY_ICONS[tool.category] || <Wrench className="h-5 w-5" />}
          </div>
          <div>
            <CardTitle className="text-base">
              <code className="font-mono">{tool.name}</code>
            </CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <p className="text-sm text-muted-foreground line-clamp-3">
          {tool.description.split('\n')[0]}
        </p>
      </CardContent>
    </Card>
  );
}

export default function ToolsPage() {
  const { t } = useTranslation('tools');
  const { t: tc } = useTranslation('common');
  const { data: toolsData, isLoading } = useTools();

  // Group tools by category
  const toolsByCategory = React.useMemo(() => {
    const grouped: Record<string, Tool[]> = {};
    if (toolsData) {
      for (const tool of toolsData.tools) {
        if (!grouped[tool.category]) {
          grouped[tool.category] = [];
        }
        grouped[tool.category].push(tool);
      }
    }
    return grouped;
  }, [toolsData]);

  return (
    <div className="container max-w-6xl py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">{t('title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('description')}
          </p>
        </div>
      </div>

      {/* Content */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5" />
            {t('availableTools')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">{tc('actions.loading')}</p>
            </div>
          ) : !toolsData || toolsData.tools.length === 0 ? (
            <EmptyState icon={Wrench} title={t('list.empty')} />
          ) : (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Info className="h-4 w-4" />
                  <span>
                    {t('builtinInfo')}
                  </span>
                </div>
                <Badge variant="outline">{t('toolsCount', { count: toolsData.tools.length })}</Badge>
              </div>

              {Object.entries(toolsByCategory).map(([category, tools]) => {
                const categoryLabel = t(`categoryLabels.${category}`, { defaultValue: category });
                const categoryDescription = t(`categoryDescriptions.${category}`, { defaultValue: '' });

                return (
                  <div key={category}>
                    <h3 className="font-medium mb-3 flex items-center gap-2">
                      <div className="p-1.5 rounded-md bg-primary/10 text-primary">
                        {CATEGORY_ICONS[category] || <Wrench className="h-4 w-4" />}
                      </div>
                      <div>
                        <span>{categoryLabel}</span>
                        <span className="text-sm text-muted-foreground ml-2">
                          ({tools.length})
                        </span>
                      </div>
                    </h3>
                    <div className="grid gap-4 md:grid-cols-2">
                      {tools.map((tool) => (
                        <ToolCard key={tool.id} tool={tool} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

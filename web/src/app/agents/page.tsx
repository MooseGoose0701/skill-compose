'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Search, Bot, Settings, Settings2, Trash2, Globe, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorBanner } from '@/components/ui/error-banner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { toast } from 'sonner';
import { useAgentPresets, useDeleteAgentPreset } from '@/hooks/use-agents';
import { useTranslation } from '@/i18n/client';
import type { AgentPreset } from '@/lib/api';

export default function AgentsPage() {
  const { t } = useTranslation('agents');
  const { t: tc } = useTranslation('common');

  const [searchQuery, setSearchQuery] = useState('');
  const { data, isLoading, error } = useAgentPresets();
  const deletePreset = useDeleteAgentPreset();

  const filteredPresets = useMemo(() =>
    data?.presets.filter(
      (preset) =>
        preset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        preset.description?.toLowerCase().includes(searchQuery.toLowerCase())
    ), [data?.presets, searchQuery]);

  // Separate user agents and meta agents
  const userAgents = useMemo(() => filteredPresets?.filter((preset) => !preset.is_system) || [], [filteredPresets]);
  const metaAgents = useMemo(() => filteredPresets?.filter((preset) => preset.is_system) || [], [filteredPresets]);

  const handleDelete = async (presetId: string) => {
    try {
      await deletePreset.mutateAsync(presetId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('delete.error'));
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Main Content */}
      <main className="flex-1 container px-4 py-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">{t('title')}</h1>
            <p className="text-muted-foreground mt-1">
              {t('description')}
            </p>
          </div>
          <div className="flex flex-col items-center gap-1">
            <Link href="/agents/new">
              <Button size="lg">
                {t('list.composeButton')}
              </Button>
            </Link>
            <span className="text-xs text-muted-foreground">
              {t('list.composeSubtext')}
            </span>
          </div>
        </div>

        {/* Search */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('list.searchPlaceholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {/* Error State */}
        {error && (
          <ErrorBanner title={tc('errors.generic')} message={(error as Error).message} className="mb-6" />
        )}

        {/* Loading State */}
        {isLoading && (
          <LoadingSkeleton variant="card-grid" count={3} />
        )}

        {/* Empty State */}
        {!isLoading && userAgents.length === 0 && metaAgents.length === 0 && (
          <EmptyState
            icon={Bot}
            title={t('list.empty')}
            description={searchQuery ? tc('empty.noResults') : t('list.emptyDescription')}
            action={!searchQuery ? (
              <div className="flex flex-col items-center gap-1">
                <Link href="/agents/new">
                  <Button size="lg">
                    {t('list.composeButton')}
                  </Button>
                </Link>
                <span className="text-xs text-muted-foreground">
                  {t('list.composeSubtext')}
                </span>
              </div>
            ) : undefined}
          />
        )}

        <TooltipProvider>
          {/* User Agents */}
          {!isLoading && userAgents.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold mb-4">{t('list.user')}</h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {userAgents.map((preset) => (
                  <AgentPresetCard
                    key={preset.id}
                    preset={preset}
                    onDelete={() => handleDelete(preset.id)}
                    t={t}
                    tc={tc}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Meta Agents */}
          {!isLoading && metaAgents.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-muted-foreground">
                <Settings2 className="h-4 w-4" />
                {t('list.meta')}
              </h2>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {metaAgents.map((preset) => (
                  <AgentPresetCard
                    key={preset.id}
                    preset={preset}
                    onDelete={() => handleDelete(preset.id)}
                    t={t}
                    tc={tc}
                  />
                ))}
              </div>
            </div>
          )}
        </TooltipProvider>

        {/* Stats */}
        {data && (
          <div className="mt-8 text-sm text-muted-foreground">
            {t('list.title')}: {filteredPresets?.length || 0} / {data.total}
          </div>
        )}
      </main>
    </div>
  );
}

function AgentPresetCard({
  preset,
  onDelete,
  t,
  tc,
}: {
  preset: AgentPreset;
  onDelete: () => void;
  t: (key: string, options?: Record<string, unknown>) => string;
  tc: (key: string) => string;
}) {
  return (
    <Card className="group hover:shadow-md transition-shadow h-full flex flex-col">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">
              <Link href={`/agents/${preset.id}`} className="hover:underline">
                {preset.name}
              </Link>
            </CardTitle>
          </div>
          <div className="flex items-center gap-1">
            {preset.is_published && (
              <Badge variant="success" className="text-xs">
                <Globe className="h-3 w-3 mr-1" />
                {tc('status.published')}
              </Badge>
            )}
            {preset.is_system && (
              <Badge variant="secondary">{t('type.meta')}</Badge>
            )}
          </div>
        </div>
        {preset.description && (
          <CardDescription className="line-clamp-2">{preset.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex-1 flex flex-col">
        <div className="space-y-2 text-sm text-muted-foreground flex-1">
          {preset.skill_ids && preset.skill_ids.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span>{tc('nav.skills')}:</span>
              {preset.skill_ids.slice(0, 3).map((skill) => (
                <Badge key={skill} variant="outline" className="text-xs">{skill}</Badge>
              ))}
              {preset.skill_ids.length > 3 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="text-xs cursor-default">+{preset.skill_ids.length - 3}</Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    <p className="text-xs">{preset.skill_ids.slice(3).join(', ')}</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          )}
          {preset.mcp_servers && preset.mcp_servers.length > 0 && (
            <div className="flex flex-wrap gap-1">
              <span>{tc('nav.mcp')}:</span>
              {preset.mcp_servers.slice(0, 2).map((server) => (
                <Badge key={server} variant="outline" className="text-xs bg-purple-50 dark:bg-purple-950">{server}</Badge>
              ))}
              {preset.mcp_servers.length > 2 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="text-xs cursor-default">+{preset.mcp_servers.length - 2}</Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    <p className="text-xs">{preset.mcp_servers.slice(2).join(', ')}</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 mt-4 pt-4 border-t">
          <Link href={`/agents/${preset.id}`} className="flex-1">
            <Button variant="outline" size="sm" className="w-full">
              <Settings className="mr-2 h-4 w-4" />
              {tc('actions.edit')}
            </Button>
          </Link>
          {preset.is_published && (
            <a href={`/published/${preset.id}`} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" aria-label={tc('status.published')}>
                <ExternalLink className="h-4 w-4" />
              </Button>
            </a>
          )}
          {!preset.is_system && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  aria-label={tc('actions.delete')}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('delete.title')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('delete.confirm', { name: preset.name })} {t('delete.description')}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={(e) => {
                      e.preventDefault();
                      onDelete();
                    }}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {tc('actions.delete')}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

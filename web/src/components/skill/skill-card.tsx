'use client';

import Image from 'next/image';
import Link from 'next/link';
import {
  FileText,
  Clock,
  Tag,
  Settings2,
  Wand2,
  MessageSquareText,
  Download,
  Network,
  SearchCheck,
  FolderPlus,
  Users,
  TrendingUp,
  FileCheck,
  RefreshCw,
  Lightbulb,
  Blocks,
  ClipboardList,
  Pin,
  Bot,
  type LucideIcon,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { formatRelativeTime } from '@/lib/formatters';
import { useTogglePin } from '@/hooks/use-skills';
import { useTranslation } from '@/i18n/client';
import { getSkillDescription } from '@/lib/seed-descriptions';
import type { Skill } from '@/types/skill';

interface SkillCardProps {
  skill: Skill;
  hasGithubUpdate?: boolean;
  agentNames?: string[];
}

const MAX_VISIBLE_TAGS = 3;

// Mapping of skill names to their default Lucide icons
const SKILL_ICONS: Record<string, LucideIcon> = {
  'skill-creator': Wand2,
  'skill-evolver': TrendingUp,
  'skill-updater': RefreshCw,
  'mcp-builder': Blocks,
  'wechat2md': MessageSquareText,
  'download-video-from-url': Download,
  'ragflow': Network,
  'trace-qa': SearchCheck,
  'topic-collector': FolderPlus,
  'topic-generator': Lightbulb,
  'topic-reviewer': ClipboardList,
  'doc-coauthoring': Users,
  'article-review': FileCheck,
};

// Helper to get the full icon URL with cache busting
function getIconUrl(iconUrl: string | null, updatedAt?: string): string | null {
  if (!iconUrl) return null;
  // If it's already a full URL, return as-is
  let url = iconUrl;
  if (!iconUrl.startsWith('http://') && !iconUrl.startsWith('https://')) {
    // Prepend the API base URL
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:62610';
    const cleanBaseUrl = baseUrl.replace(/\/api\/v1\/?$/, '').replace(/\/$/, '');
    url = `${cleanBaseUrl}${iconUrl}`;
  }
  // Add cache busting param based on updated_at
  if (updatedAt) {
    const cacheBuster = new Date(updatedAt).getTime();
    url += `?v=${cacheBuster}`;
  }
  return url;
}

export function SkillCard({ skill, hasGithubUpdate, agentNames }: SkillCardProps) {
  const { t } = useTranslation('skills');
  const { t: tc } = useTranslation('common');
  const togglePin = useTogglePin();
  const isMeta = skill.skill_type === 'meta';  // undefined defaults to user
  const tags = skill.tags || [];
  const visibleTags = tags.slice(0, MAX_VISIBLE_TAGS);
  const overflowCount = tags.length - MAX_VISIBLE_TAGS;
  const iconUrl = getIconUrl(skill.icon_url, skill.updated_at);

  const handleTogglePin = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    togglePin.mutate(skill.name);
  };

  return (
    <Link href={`/skills/${skill.name}`}>
      <Card className={`h-full flex flex-col hover:border-primary/50 transition-colors cursor-pointer ${isMeta ? 'bg-muted/30' : ''}`}>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            {/* Icon - larger size like reference */}
            <div className="flex-shrink-0">
              {iconUrl ? (
                <div className="relative h-12 w-12 rounded-lg overflow-hidden bg-muted/30">
                  <Image
                    src={iconUrl}
                    alt={`${skill.name} icon`}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                </div>
              ) : (
                <div className={`h-12 w-12 rounded-lg flex items-center justify-center ${isMeta ? 'bg-primary/10' : 'bg-muted/50'}`}>
                  {(() => {
                    const SkillIcon = SKILL_ICONS[skill.name] || (isMeta ? Settings2 : FileText);
                    return <SkillIcon className={`h-6 w-6 ${isMeta ? 'text-primary' : 'text-muted-foreground'}`} />;
                  })()}
                </div>
              )}
            </div>
            {/* Title and badge - vertically centered */}
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <h3
                className="font-semibold truncate select-text cursor-text"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}
              >{skill.name}</h3>
              {isMeta && (
                <Badge variant="outline" className="text-xs flex-shrink-0">Meta</Badge>
              )}
            </div>
            {/* Pin button */}
            {!isMeta && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 flex-shrink-0"
                onClick={handleTogglePin}
                title={skill.is_pinned ? t('card.unpin') : t('card.pin')}
              >
                <Pin className={`h-3.5 w-3.5 ${skill.is_pinned ? 'fill-current text-primary' : 'text-muted-foreground'}`} />
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="flex flex-col flex-1">
          <p className="text-sm text-muted-foreground line-clamp-2 mb-3 min-h-[2.5rem]">
            {getSkillDescription(t, skill.name, skill.description) || '\u00A0'}
          </p>
          <div className="flex flex-wrap gap-1.5 mb-3">
            {skill.category && (
              <Badge variant="info" className="text-xs font-normal">
                {skill.category}
              </Badge>
            )}
            {visibleTags.map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs font-normal">
                {tag}
              </Badge>
            ))}
            {overflowCount > 0 && (
              <Badge variant="outline" className="text-xs font-normal">
                +{overflowCount}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground mt-auto">
            {skill.current_version && (
              <div className="flex items-center gap-1">
                <Tag className="h-3 w-3" />
                <span>v{skill.current_version}</span>
                {hasGithubUpdate && (
                  <span
                    className="inline-block w-2 h-2 rounded-full bg-amber-400 dark:bg-amber-500"
                    title={t('card.githubUpdateAvailable')}
                  />
                )}
              </div>
            )}
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              <span>{formatRelativeTime(skill.updated_at, tc)}</span>
            </div>
            {!isMeta && agentNames && agentNames.length > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1 ml-auto px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium">
                    <Bot className="h-3 w-3" />
                    <span>{agentNames.length}</span>
                  </div>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p>{t('card.usedByAgents', { count: agentNames.length })}: {agentNames.join(', ')}</p>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

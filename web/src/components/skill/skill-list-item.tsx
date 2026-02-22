'use client';

import Link from 'next/link';
import {
  FileText,
  Clock,
  Tag,
  Settings2,
  Pin,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatRelativeTime } from '@/lib/utils';
import { useTogglePin } from '@/hooks/use-skills';
import { useTranslation } from '@/i18n/client';
import type { Skill } from '@/types/skill';

interface SkillListItemProps {
  skill: Skill;
  hasGithubUpdate?: boolean;
}

const MAX_VISIBLE_TAGS = 2;

export function SkillListItem({ skill, hasGithubUpdate }: SkillListItemProps) {
  const { t } = useTranslation('skills');
  const togglePin = useTogglePin();
  const isMeta = skill.skill_type === 'meta';
  const tags = skill.tags || [];
  const visibleTags = tags.slice(0, MAX_VISIBLE_TAGS);
  const overflowCount = tags.length - MAX_VISIBLE_TAGS;

  const handleTogglePin = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    togglePin.mutate(skill.name);
  };

  return (
    <Link href={`/skills/${skill.name}`}>
      <Card className={`hover:border-primary/50 transition-colors cursor-pointer ${isMeta ? 'bg-muted/30' : ''}`}>
        <div className="flex items-center gap-3 p-3">
          {/* Icon */}
          <div className={`h-8 w-8 rounded-md flex items-center justify-center flex-shrink-0 ${isMeta ? 'bg-primary/10' : 'bg-muted/50'}`}>
            {isMeta ? (
              <Settings2 className="h-4 w-4 text-primary" />
            ) : (
              <FileText className="h-4 w-4 text-muted-foreground" />
            )}
          </div>

          {/* Name */}
          <div className="flex items-center gap-2 min-w-0 w-48 flex-shrink-0">
            <span className="font-medium truncate text-sm">{skill.name}</span>
            {isMeta && (
              <Badge variant="outline" className="text-xs flex-shrink-0">Meta</Badge>
            )}
          </div>

          {/* Description */}
          <p className="text-sm text-muted-foreground truncate flex-1 min-w-0">
            {skill.description || '\u00A0'}
          </p>

          {/* Category badge */}
          {skill.category && (
            <Badge variant="info" className="text-xs font-normal flex-shrink-0">
              {skill.category}
            </Badge>
          )}

          {/* Tags */}
          <div className="flex gap-1 flex-shrink-0">
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

          {/* Version */}
          {skill.current_version && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground flex-shrink-0">
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

          {/* Updated time */}
          <div className="flex items-center gap-1 text-xs text-muted-foreground flex-shrink-0 w-24">
            <Clock className="h-3 w-3" />
            <span>{formatRelativeTime(skill.updated_at)}</span>
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
      </Card>
    </Link>
  );
}

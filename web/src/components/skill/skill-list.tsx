'use client';

import { useState, useMemo } from 'react';
import { FileText, Pin, ChevronRight, Settings2 } from 'lucide-react';
import { SkillCard } from './skill-card';
import { SkillListItem } from './skill-list-item';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import { Badge } from '@/components/ui/badge';
import { TooltipProvider } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { Skill } from '@/types/skill';
import type { ViewMode } from '@/app/skills/page';
import { useTranslation } from '@/i18n/client';
import { useGithubUpdateStatus } from '@/hooks/use-skills';
import { useAgentPresets } from '@/hooks/use-agents';

interface SkillListProps {
  skills: Skill[];
  isLoading?: boolean;
  viewMode?: ViewMode;
  groupByCategory?: boolean;
  allCategories?: string[];
}

export function SkillList({
  skills,
  isLoading,
  viewMode = 'grid',
  groupByCategory = false,
  allCategories = [],
}: SkillListProps) {
  const { t } = useTranslation('skills');
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  // Check GitHub update status
  const githubSkillNames = useMemo(
    () => skills.filter((s) => s.source?.startsWith('https://github.com')).map((s) => s.name),
    [skills]
  );
  const { data: githubStatus } = useGithubUpdateStatus(githubSkillNames.length > 0);
  const githubUpdateMap = githubStatus?.results;

  // Build skill → agent names map
  const { data: agents } = useAgentPresets();
  const agentReferencesMap = useMemo(() => {
    const map = new Map<string, string[]>();
    if (!agents?.presets) return map;
    for (const agent of agents.presets.filter((a) => !a.is_system)) {
      if (agent.skill_ids) {
        for (const skillName of agent.skill_ids) {
          if (!map.has(skillName)) {
            map.set(skillName, []);
          }
          map.get(skillName)!.push(agent.name);
        }
      }
    }
    return map;
  }, [agents]);

  // Separate user and meta skills (treat undefined as 'user')
  const userSkills = skills.filter((s) => !s.skill_type || s.skill_type !== 'meta');
  const metaSkills = skills.filter((s) => s.skill_type === 'meta');

  // Sort meta skills: skill-creator first, then skill-updater, then skill-evolver
  const metaSkillOrder = ['skill-creator', 'skill-updater', 'skill-evolver'];
  const sortedMetaSkills = [...metaSkills].toSorted((a, b) => {
    const aIndex = metaSkillOrder.indexOf(a.name);
    const bIndex = metaSkillOrder.indexOf(b.name);
    if (aIndex === -1 && bIndex === -1) return a.name.localeCompare(b.name);
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  });

  // Separate pinned and unpinned user skills
  const pinnedUserSkills = userSkills.filter((s) => s.is_pinned);
  const unpinnedUserSkills = userSkills.filter((s) => !s.is_pinned);

  // Group unpinned user skills by category (Map for O(1) lookup)
  const UNCATEGORIZED_KEY = '__uncategorized__';
  const categoryGroups = useMemo(() => {
    if (!groupByCategory) return null;

    const groups = new Map<string, Skill[]>();

    for (const cat of allCategories) {
      groups.set(cat, []);
    }

    for (const skill of unpinnedUserSkills) {
      const key = skill.category || UNCATEGORIZED_KEY;
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(skill);
    }

    // Build ordered result: allCategories order first, then uncategorized last
    const ordered = new Map<string, Skill[]>();
    for (const cat of allCategories) {
      const items = groups.get(cat);
      if (items && items.length > 0) {
        ordered.set(cat, items);
      }
    }
    const uncategorized = groups.get(UNCATEGORIZED_KEY);
    if (uncategorized && uncategorized.length > 0) {
      ordered.set(UNCATEGORIZED_KEY, uncategorized);
    }

    return ordered;
  }, [groupByCategory, unpinnedUserSkills, allCategories]);

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });
  };

  if (isLoading) {
    return <LoadingSkeleton variant="card-grid" count={6} />;
  }

  if (skills.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title={t('list.empty')}
        description={t('list.emptyDescription')}
      />
    );
  }

  const renderGrid = (items: Skill[]) => (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {items.map((skill) => (
        <SkillCard key={skill.id} skill={skill} hasGithubUpdate={githubUpdateMap?.[skill.name]?.has_update} agentNames={agentReferencesMap.get(skill.name)} />
      ))}
    </div>
  );

  const renderList = (items: Skill[]) => (
    <div className="space-y-2">
      {items.map((skill) => (
        <SkillListItem key={skill.id} skill={skill} hasGithubUpdate={githubUpdateMap?.[skill.name]?.has_update} agentNames={agentReferencesMap.get(skill.name)} />
      ))}
    </div>
  );

  const renderItems = viewMode === 'grid' ? renderGrid : renderList;

  const shouldGroupCategories = groupByCategory && categoryGroups && categoryGroups.size > 0;

  return (
    <TooltipProvider delayDuration={300}>
    <div className="space-y-8">
      {/* Pinned User Skills */}
      {pinnedUserSkills.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Pin className="h-4 w-4" />
            {t('list.pinned')}
          </h2>
          {renderItems(pinnedUserSkills)}
        </div>
      )}

      {/* User Skills — grouped by category or flat */}
      {shouldGroupCategories ? (
        Array.from(categoryGroups.entries()).map(([category, items]) => {
          const isCollapsed = collapsedGroups.has(category);
          const displayName =
            category === UNCATEGORIZED_KEY
              ? t('list.uncategorized')
              : category;

          return (
            <div key={category}>
              <button
                onClick={() => toggleGroup(category)}
                aria-expanded={!isCollapsed}
                className="flex items-center gap-2 text-lg font-semibold mb-4 hover:text-foreground/80 transition-colors w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
              >
                <ChevronRight
                  className={cn(
                    'h-5 w-5 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none',
                    !isCollapsed && 'rotate-90'
                  )}
                />
                <span className="text-wrap-balance">{displayName}</span>
                <Badge variant="secondary" className="ml-1 text-xs font-normal tabular-nums">
                  {items.length}
                </Badge>
              </button>
              {!isCollapsed && renderItems(items)}
            </div>
          );
        })
      ) : (
        unpinnedUserSkills.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-4">{t('list.userSkills')}</h2>
            {renderItems(unpinnedUserSkills)}
          </div>
        )
      )}

      {/* Meta Skills — at the bottom, always visible */}
      {sortedMetaSkills.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2 text-muted-foreground">
            <Settings2 className="h-4 w-4" />
            {t('list.metaSkills')}
          </h2>
          {renderItems(sortedMetaSkills)}
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}

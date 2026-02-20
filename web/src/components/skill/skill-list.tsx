'use client';

import { useState, useMemo } from 'react';
import { FileText, Pin, ChevronRight } from 'lucide-react';
import { SkillCard } from './skill-card';
import { SkillListItem } from './skill-list-item';
import { LoadingSkeleton } from '@/components/ui/loading-skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { Skill } from '@/types/skill';
import type { ViewMode } from '@/app/skills/page';
import { useTranslation } from '@/i18n/client';

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
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['__meta__']));

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
        <SkillCard key={skill.id} skill={skill} />
      ))}
    </div>
  );

  const renderList = (items: Skill[]) => (
    <div className="space-y-2">
      {items.map((skill) => (
        <SkillListItem key={skill.id} skill={skill} />
      ))}
    </div>
  );

  const renderItems = viewMode === 'grid' ? renderGrid : renderList;

  const isMetaCollapsed = collapsedGroups.has('__meta__');
  const shouldGroupCategories = groupByCategory && categoryGroups && categoryGroups.size > 0;

  return (
    <div className="space-y-8">
      {/* Meta Skills — distinct container, collapsed by default */}
      {sortedMetaSkills.length > 0 && (
        <div className="rounded-lg border border-dashed border-border bg-muted/40 dark:bg-muted/20 dark:ring-1 dark:ring-white/[0.04]">
          <button
            onClick={() => toggleGroup('__meta__')}
            aria-expanded={!isMetaCollapsed}
            className="flex items-center gap-2 w-full text-left px-4 py-3 text-base font-semibold text-muted-foreground hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-lg"
          >
            <ChevronRight
              className={cn(
                'h-4 w-4 flex-shrink-0 transition-transform duration-200 motion-reduce:transition-none',
                !isMetaCollapsed && 'rotate-90'
              )}
            />
            <span>{t('list.metaSkills')}</span>
            <Badge variant="secondary" className="text-xs font-normal tabular-nums">
              {sortedMetaSkills.length}
            </Badge>
          </button>
          {!isMetaCollapsed && (
            <div className="px-4 pb-4">
              {renderItems(sortedMetaSkills)}
            </div>
          )}
        </div>
      )}

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
    </div>
  );
}

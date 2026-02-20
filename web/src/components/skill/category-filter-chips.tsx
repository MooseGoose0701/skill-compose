'use client';

import { useCallback } from 'react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n/client';

interface CategoryFilterChipsProps {
  categories: string[];
  selectedCategories: Set<string>;
  onChange: (categories: Set<string>) => void;
}

export function CategoryFilterChips({
  categories,
  selectedCategories,
  onChange,
}: CategoryFilterChipsProps) {
  const { t } = useTranslation('skills');

  const isAllSelected = selectedCategories.size === 0;

  const handleAllClick = useCallback(() => {
    onChange(new Set());
  }, [onChange]);

  const handleCategoryClick = useCallback(
    (category: string) => {
      const next = new Set(selectedCategories);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      // If all categories individually selected, normalize to empty set (= "All")
      if (next.size === categories.length) {
        onChange(new Set());
      } else {
        onChange(next);
      }
    },
    [selectedCategories, categories.length, onChange]
  );

  if (categories.length === 0) return null;

  const chipBase =
    'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium transition-colors select-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';
  const chipSelected =
    'border-transparent bg-primary text-primary-foreground hover:bg-primary/90';
  const chipUnselected =
    'border-border bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground';

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={t('list.filterByCategory')}>
      <button
        type="button"
        className={cn(chipBase, isAllSelected ? chipSelected : chipUnselected)}
        onClick={handleAllClick}
      >
        {t('list.allCategories')}
      </button>
      {categories.map((category) => {
        const isActive = selectedCategories.has(category);
        return (
          <button
            key={category}
            type="button"
            className={cn(chipBase, isActive ? chipSelected : chipUnselected)}
            onClick={() => handleCategoryClick(category)}
          >
            {category}
          </button>
        );
      })}
    </div>
  );
}

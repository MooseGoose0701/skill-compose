'use client';

import { useState, useRef, useEffect } from 'react';
import { Pencil, Check, X, Github, RefreshCw, ExternalLink } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { skillsApi } from '@/lib/api';
import { formatDateTime } from '@/lib/formatters';
import { SKILL_CATEGORIES } from '@/lib/constants';
import { useCategories, skillKeys } from '@/hooks/use-skills';
import { SkillTypeBadge } from './skill-type-badge';
import { SkillIconEditor } from './skill-icon-editor';
import { useTranslation } from '@/i18n/client';
import { getSkillDescription } from '@/lib/seed-descriptions';
import type { Skill } from '@/types/skill';

function InlineEdit({
  label,
  value,
  fieldKey,
  skillName,
  placeholder = '—',
  multiline = false,
  renderValue,
}: {
  label: string;
  value: string | null | undefined;
  fieldKey: string;
  skillName: string;
  placeholder?: string;
  multiline?: boolean;
  renderValue?: (value: string) => React.ReactNode;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [input, setInput] = useState(value || '');
  const [saving, setSaving] = useState(false);

  const startEditing = () => {
    setInput(value || '');
    setEditing(true);
  };

  const cancel = () => {
    setEditing(false);
    setInput(value || '');
  };

  const save = async () => {
    setSaving(true);
    try {
      await skillsApi.update(skillName, { [fieldKey]: input });
      queryClient.invalidateQueries({ queryKey: ['skill', skillName] });
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      setEditing(false);
    } catch (e) {
      console.error(`Failed to save ${fieldKey}:`, e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-medium text-muted-foreground">{label}</h4>
        {!editing && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={startEditing}
          >
            <Pencil className="h-3 w-3" />
          </Button>
        )}
      </div>
      {editing ? (
        <div className="flex items-center gap-2 mt-1">
          {multiline ? (
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[60px] resize-y"
              onKeyDown={(e) => {
                if (e.key === 'Escape') cancel();
              }}
              disabled={saving}
              autoFocus
            />
          ) : (
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={placeholder}
              className="text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  save();
                }
                if (e.key === 'Escape') cancel();
              }}
              disabled={saving}
              autoFocus
            />
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 flex-shrink-0"
            onClick={save}
            disabled={saving}
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0 flex-shrink-0"
            onClick={cancel}
            disabled={saving}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <div className="mt-1">
          {(() => {
            const rendered = renderValue ? renderValue(value || '') : null;
            if (rendered) return rendered;
            if (value) return <p className="text-sm">{value}</p>;
            return <p className="text-sm text-muted-foreground">{placeholder}</p>;
          })()}
        </div>
      )}
    </div>
  );
}

function CategoryEdit({ skill }: { skill: Skill }) {
  const queryClient = useQueryClient();
  const { t } = useTranslation('skills');
  const { data: existingCategories } = useCategories();
  const [editing, setEditing] = useState(false);
  const [input, setInput] = useState(skill.category || '');
  const [saving, setSaving] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Merge predefined + existing DB categories, deduplicated
  const allCategories = Array.from(
    new Set([
      ...SKILL_CATEGORIES,
      ...(existingCategories || []),
    ])
  ).sort();

  const filtered = input
    ? allCategories.filter((c) =>
        c.toLowerCase().includes(input.toLowerCase())
      )
    : allCategories;

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const startEditing = () => {
    setInput(skill.category || '');
    setEditing(true);
    setShowSuggestions(true);
  };

  const cancel = () => {
    setEditing(false);
    setInput(skill.category || '');
    setShowSuggestions(false);
  };

  const save = async (value: string) => {
    setSaving(true);
    try {
      await skillsApi.update(skill.name, { category: value });
      queryClient.invalidateQueries({ queryKey: ['skill', skill.name] });
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      setEditing(false);
      setShowSuggestions(false);
    } catch (e) {
      console.error('Failed to save category:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-medium text-muted-foreground">{t('overview.category')}</h4>
        {!editing && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0"
            onClick={startEditing}
          >
            <Pencil className="h-3 w-3" />
          </Button>
        )}
      </div>
      {editing ? (
        <div className="relative mt-1" ref={wrapperRef}>
          <div className="flex items-center gap-2">
            <Input
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              placeholder={t('overview.categoryPlaceholder')}
              className="text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  save(input.trim());
                }
                if (e.key === 'Escape') cancel();
              }}
              disabled={saving}
              autoFocus
            />
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 flex-shrink-0"
              onClick={() => save(input.trim())}
              disabled={saving}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 flex-shrink-0"
              onClick={cancel}
              disabled={saving}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          {showSuggestions && filtered.length > 0 && (
            <div className="absolute z-50 mt-1 w-full max-h-[200px] overflow-y-auto rounded-md border bg-popover shadow-md">
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent cursor-pointer"
                onClick={() => {
                  setInput('');
                  save('');
                }}
              >
                {t('overview.noCategory')}
              </button>
              {filtered.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  className={`w-full text-left px-3 py-1.5 text-sm hover:bg-accent cursor-pointer ${
                    cat === input ? 'bg-accent font-medium' : ''
                  }`}
                  onClick={() => {
                    setInput(cat);
                    save(cat);
                  }}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <p className="mt-1 text-sm">
          {skill.category || <span className="text-muted-foreground">{t('overview.noCategory')}</span>}
        </p>
      )}
    </div>
  );
}

export function SkillOverview({ skill }: { skill: Skill }) {
  const { t: ts } = useTranslation('skills');
  const queryClient = useQueryClient();
  const [editingTags, setEditingTags] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const tags = skill.tags || [];
  const isGitHubSource = skill.source?.startsWith('https://github.com');

  const startEditing = () => {
    setTagInput(tags.join(', '));
    setEditingTags(true);
  };

  const cancelEditing = () => {
    setEditingTags(false);
    setTagInput('');
  };

  const saveTags = async () => {
    setSaving(true);
    try {
      const newTags = tagInput
        .split(',')
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);
      await skillsApi.update(skill.name, { tags: newTags });
      queryClient.invalidateQueries({ queryKey: ['skill', skill.name] });
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      setEditingTags(false);
    } catch (e) {
      console.error('Failed to save tags:', e);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateFromGitHub = async () => {
    setUpdating(true);
    setUpdateMessage(null);
    try {
      const result = await skillsApi.updateFromGitHub(skill.name);
      if (result.new_version) {
        setUpdateMessage({
          type: 'success',
          text: `Updated to v${result.new_version} (${result.changes?.length || 0} files changed)`,
        });
        queryClient.invalidateQueries({ queryKey: ['versions', skill.name] });
        queryClient.invalidateQueries({ queryKey: ['changelogs', skill.name] });
      } else {
        setUpdateMessage({
          type: 'success',
          text: result.message,
        });
      }
      // Always refresh skill data (author may have changed even without file changes)
      queryClient.invalidateQueries({ queryKey: ['skill', skill.name] });
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      queryClient.invalidateQueries({ queryKey: skillKeys.githubStatus() });
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Update failed';
      setUpdateMessage({
        type: 'error',
        text: message,
      });
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Icon Editor */}
      <SkillIconEditor skill={skill} />

      <div className="grid grid-cols-2 gap-4">
        {/* Row 1: Source and Author */}
        <div className="col-span-2 sm:col-span-1">
          <InlineEdit
            label={ts('overview.source')}
            value={skill.source}
            fieldKey="source"
            skillName={skill.name}
            placeholder="—"
            renderValue={(val) =>
              val.startsWith('https://github.com') ? (
                <a
                  href={val}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1 max-w-full"
                  title={val}
                >
                  <Github className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="truncate">
                    {val.replace('https://github.com/', '')}
                  </span>
                  <ExternalLink className="h-3 w-3 flex-shrink-0" />
                </a>
              ) : (
                <p className="text-sm">{val}</p>
              )
            }
          />
          {isGitHubSource && (
            <div className="mt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleUpdateFromGitHub}
                disabled={updating}
                className="gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${updating ? 'animate-spin' : ''}`} />
                {updating ? ts('overview.checking') : ts('overview.updateFromGitHub')}
              </Button>
              {updateMessage && (
                <p
                  className={`mt-1 text-sm ${
                    updateMessage.type === 'success'
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-red-600 dark:text-red-400'
                  }`}
                >
                  {updateMessage.text}
                </p>
              )}
            </div>
          )}
        </div>
        <div>
          <InlineEdit
            label={ts('overview.author')}
            value={skill.author}
            fieldKey="author"
            skillName={skill.name}
            placeholder="—"
          />
        </div>

        {/* Row 2: Type and Category */}
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">{ts('overview.type')}</h4>
          <div className="mt-1">
            <SkillTypeBadge skillType={skill.skill_type} />
          </div>
        </div>
        {skill.skill_type !== 'meta' && (
          <CategoryEdit skill={skill} />
        )}

        {/* Row 3: Current Version */}
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">
            {ts('overview.currentVersion')}
          </h4>
          <p className="mt-1 text-sm">
            {skill.current_version || ts('overview.noVersion')}
          </p>
        </div>

        {/* Row 4: Created and Updated */}
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">{ts('overview.createdAt')}</h4>
          <p className="mt-1 text-sm">{formatDateTime(skill.created_at)}</p>
        </div>
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">{ts('overview.updatedAt')}</h4>
          <p className="mt-1 text-sm">{formatDateTime(skill.updated_at)}</p>
        </div>
      </div>

      {/* Description - always shown, editable */}
      <InlineEdit
        label={ts('overview.description')}
        value={skill.description}
        fieldKey="description"
        skillName={skill.name}
        placeholder={ts('overview.noDescription')}
        multiline
        renderValue={(val) => {
          const desc = getSkillDescription(ts, skill.name, val || null);
          return desc ? <p className="text-sm">{desc}</p> : null;
        }}
      />

      <div>
        <div className="flex items-center gap-2 mb-1">
          <h4 className="text-sm font-medium text-muted-foreground">{ts('overview.tags')}</h4>
          {!editingTags && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0"
              onClick={startEditing}
            >
              <Pencil className="h-3 w-3" />
            </Button>
          )}
        </div>
        {editingTags ? (
          <div className="flex items-center gap-2">
            <Input
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              placeholder={ts('overview.tagsPlaceholder')}
              className="text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  saveTags();
                }
                if (e.key === 'Escape') cancelEditing();
              }}
              disabled={saving}
              autoFocus
            />
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={saveTags}
              disabled={saving}
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={cancelEditing}
              disabled={saving}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {tags.length > 0 ? (
              tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs font-normal">
                  {tag}
                </Badge>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">{ts('overview.noTags')}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

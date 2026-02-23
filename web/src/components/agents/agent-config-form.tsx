'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Save, Trash2 } from 'lucide-react';
import { useTranslation } from '@/i18n/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { MultiSelect, MultiSelectOptionGroup } from '@/components/ui/multi-select';
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
import { ModelSelect, ExecutorSelect } from '@/components/chat/selects';
import { useExecutors } from '@/hooks/use-executors';
import { skillsApi, toolsApi, mcpApi, modelsApi } from '@/lib/api';

// ─── Types ───────────────────────────────────────────────

export interface AgentFormValues {
  name: string;
  description: string;
  system_prompt: string;
  skill_ids: string[];
  builtin_tools: string[];
  mcp_servers: string[];
  max_turns: number;
  model_provider: string | null;
  model_name: string | null;
  executor_name: string | null;
}

interface AgentConfigFormProps {
  mode: 'create' | 'edit';
  initialValues?: Partial<AgentFormValues>;
  isSystem?: boolean;
  isProcessing?: boolean;
  isSaving?: boolean;
  isDeleting?: boolean;
  hasChanges?: boolean;
  onSubmit: (values: AgentFormValues) => void;
  onDelete?: () => void;
  onChange?: () => void;
  presetName?: string;
}

// ─── Component ───────────────────────────────────────────

export function AgentConfigForm({
  mode,
  initialValues,
  isSystem = false,
  isProcessing = false,
  isSaving = false,
  isDeleting = false,
  hasChanges: externalHasChanges,
  onSubmit,
  onDelete,
  onChange,
  presetName,
}: AgentConfigFormProps) {
  const { t } = useTranslation('agents');
  const { t: tc } = useTranslation('common');

  // Form state
  const [name, setName] = useState(initialValues?.name || '');
  const [description, setDescription] = useState(initialValues?.description || '');
  const [systemPrompt, setSystemPrompt] = useState(initialValues?.system_prompt || '');
  const [selectedSkills, setSelectedSkills] = useState<string[]>(initialValues?.skill_ids || []);
  const [selectedTools, setSelectedTools] = useState<string[]>(initialValues?.builtin_tools || []);
  const [selectedMcpServers, setSelectedMcpServers] = useState<string[]>(initialValues?.mcp_servers || []);
  const [maxTurns, setMaxTurns] = useState(initialValues?.max_turns || 60);
  const [selectedModelProvider, setSelectedModelProvider] = useState<string | null>(initialValues?.model_provider || null);
  const [selectedModelName, setSelectedModelName] = useState<string | null>(initialValues?.model_name || null);
  const [selectedExecutorName, setSelectedExecutorName] = useState<string | null>(initialValues?.executor_name || null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [internalHasChanges, setInternalHasChanges] = useState(false);

  // Initialization flags for create mode defaults
  const toolsInitialized = useRef(false);
  const mcpInitialized = useRef(false);
  const skillsInitialized = useRef(false);

  const hasChanges = externalHasChanges ?? internalHasChanges;

  // Fetch available options
  const { data: skillsData } = useQuery({
    queryKey: ['registry-skills-list'],
    queryFn: () => skillsApi.list(),
  });

  const { data: toolsData } = useQuery({
    queryKey: ['tools-list'],
    queryFn: () => toolsApi.list(),
  });

  const { data: mcpData } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => mcpApi.listServers(),
  });

  const { data: modelsData } = useQuery({
    queryKey: ['models-providers'],
    queryFn: () => modelsApi.listProviders(),
  });

  const { data: executorsData } = useExecutors();

  const skills = skillsData?.skills || [];
  const executors = executorsData?.executors || [];
  const tools = toolsData?.tools || [];
  const mcpServers = mcpData?.servers || [];
  const modelProviders = modelsData?.providers || [];

  // Organize skills into groups
  const skillGroups: MultiSelectOptionGroup[] = useMemo(() => {
    const metaSkills = skills.filter((s) => s.skill_type === 'meta');
    const userSkills = skills.filter((s) => s.skill_type !== 'meta');
    const groups: MultiSelectOptionGroup[] = [];

    if (metaSkills.length > 0) {
      groups.push({
        label: t('create.skillGroups.meta'),
        options: metaSkills.map((skill) => ({
          value: skill.name,
          label: skill.name,
          description: skill.description?.slice(0, 50),
        })),
      });
    }

    if (userSkills.length > 0) {
      const sorted = [...userSkills].sort((a, b) => a.name.localeCompare(b.name));
      groups.push({
        label: t('create.skillGroups.user'),
        options: sorted.map((skill) => ({
          value: skill.name,
          label: skill.name,
          description: skill.description?.slice(0, 50),
        })),
      });
    }

    return groups;
  }, [skills, t]);

  // Sync form from initialValues when they change (edit mode)
  useEffect(() => {
    if (mode === 'edit' && initialValues) {
      setName(initialValues.name || '');
      setDescription(initialValues.description || '');
      setSystemPrompt(initialValues.system_prompt || '');
      setSelectedSkills(initialValues.skill_ids || []);
      // null means all tools enabled - select all available tools
      if (initialValues.builtin_tools === undefined || initialValues.builtin_tools === null) {
        if (tools.length > 0) setSelectedTools(tools.map(t => t.name));
      } else {
        setSelectedTools(initialValues.builtin_tools || []);
      }
      setSelectedMcpServers(initialValues.mcp_servers || []);
      setMaxTurns(initialValues.max_turns || 60);
      setSelectedModelProvider(initialValues.model_provider || null);
      setSelectedModelName(initialValues.model_name || null);
      setSelectedExecutorName(initialValues.executor_name || null);
    }
  }, [initialValues]); // eslint-disable-line react-hooks/exhaustive-deps

  // Create mode defaults: all meta skills
  useEffect(() => {
    if (mode === 'create' && skills.length > 0 && !skillsInitialized.current) {
      skillsInitialized.current = true;
      const metaSkillNames = skills.filter((s) => s.skill_type === 'meta').map((s) => s.name);
      setSelectedSkills(metaSkillNames);
    }
  }, [skills, mode]);

  // Create mode defaults: all tools
  useEffect(() => {
    if (mode === 'create' && tools.length > 0 && !toolsInitialized.current) {
      toolsInitialized.current = true;
      setSelectedTools(tools.map((t) => t.name));
    }
  }, [tools, mode]);

  // Create mode defaults: time + tavily MCP servers
  useEffect(() => {
    if (mode === 'create' && mcpServers.length > 0 && !mcpInitialized.current) {
      mcpInitialized.current = true;
      const defaults = mcpServers.filter((s) => ['time', 'tavily'].includes(s.name)).map((s) => s.name);
      setSelectedMcpServers(defaults);
    }
  }, [mcpServers, mode]);

  const handleFieldChange = <T,>(setter: React.Dispatch<React.SetStateAction<T>>, value: T) => {
    setter(value);
    setInternalHasChanges(true);
    onChange?.();
  };

  const validateName = (value: string): string | null => {
    if (!value) return t('create.nameRequired');
    if (value.length < 2) return t('create.nameMinLength');
    if (value.length > 128) return t('create.nameMaxLength');
    return null;
  };

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();

    if (mode === 'create') {
      const nameError = validateName(name);
      if (nameError) {
        setErrors({ name: nameError });
        return;
      }
    }

    setErrors({});
    onSubmit({
      name,
      description,
      system_prompt: systemPrompt,
      skill_ids: selectedSkills,
      builtin_tools: selectedTools,
      mcp_servers: selectedMcpServers,
      max_turns: maxTurns,
      model_provider: selectedModelProvider,
      model_name: selectedModelName,
      executor_name: selectedExecutorName,
    });
  };

  const setSubmitError = (msg: string) => {
    setErrors({ submit: msg });
  };

  // Expose setSubmitError for parent
  // Not needed: parent handles errors via onSubmit catch

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Name */}
      <div className="space-y-2">
        <Label htmlFor="name">
          {mode === 'create' ? t('create.name') : t('detail.name')}
          {mode === 'create' && <span className="text-destructive"> *</span>}
        </Label>
        <Input
          id="name"
          placeholder={mode === 'create' ? t('create.namePlaceholderForm') : undefined}
          value={name}
          onChange={(e) => {
            handleFieldChange(setName, e.target.value);
            if (mode === 'create') setErrors((prev) => ({ ...prev, name: '' }));
          }}
          className={errors.name ? 'border-destructive' : ''}
          disabled={isProcessing}
        />
        {errors.name && (
          <p className="text-xs text-destructive">{errors.name}</p>
        )}
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description">
          {mode === 'create' ? t('create.description') : t('detail.description')}
        </Label>
        <Textarea
          id="description"
          placeholder={mode === 'create' ? t('create.descriptionPlaceholderForm') : undefined}
          value={description}
          onChange={(e) => handleFieldChange(setDescription, e.target.value)}
          rows={2}
          disabled={isProcessing}
        />
      </div>

      {/* System Prompt */}
      <div className="space-y-2">
        <Label htmlFor="system-prompt">{t('create.systemPromptLabel')}</Label>
        <Textarea
          id="system-prompt"
          placeholder={mode === 'create' ? t('create.systemPromptPlaceholderForm') : t('detail.systemPromptPlaceholder')}
          value={systemPrompt}
          onChange={(e) => handleFieldChange(setSystemPrompt, e.target.value)}
          rows={4}
          disabled={isProcessing}
        />
        <p className="text-xs text-muted-foreground">
          {mode === 'create' ? t('create.systemPromptHelp') : t('detail.systemPromptHelp')}
        </p>
      </div>

      {/* Skills */}
      <div className="space-y-2">
        <Label>{mode === 'create' ? t('create.skills') : t('detail.skills')}</Label>
        <MultiSelect
          options={[]}
          groups={skillGroups}
          selected={selectedSkills}
          onChange={(value) => handleFieldChange(setSelectedSkills, value)}
          placeholder={t('create.skillsPlaceholder')}
          emptyText={t('create.skillsEmpty')}
          disabled={isProcessing}
          searchable
          searchPlaceholder={t('create.skillsFilterPlaceholder')}
        />
      </div>

      {/* Built-in Tools */}
      <div className="space-y-2">
        <Label>{mode === 'create' ? t('create.tools') : t('detail.tools')}</Label>
        <MultiSelect
          options={tools.map((tool) => ({
            value: tool.name,
            label: tool.name,
            description: tool.description?.slice(0, 50),
          }))}
          selected={selectedTools}
          onChange={(value) => handleFieldChange(setSelectedTools, value)}
          placeholder={t('create.toolsPlaceholder')}
          emptyText={t('create.toolsEmpty')}
          disabled={isProcessing}
        />
      </div>

      {/* MCP Servers */}
      <div className="space-y-2">
        <Label>{mode === 'create' ? t('create.mcpServers') : t('detail.mcpServers')}</Label>
        <MultiSelect
          options={mcpServers.map((server) => ({
            value: server.name,
            label: server.display_name,
            description: server.description?.slice(0, 50),
          }))}
          selected={selectedMcpServers}
          onChange={(value) => handleFieldChange(setSelectedMcpServers, value)}
          placeholder={t('create.mcpPlaceholder')}
          emptyText={t('create.mcpEmpty')}
          disabled={isProcessing}
        />
      </div>

      {/* Max Turns */}
      <div className="space-y-2">
        <Label htmlFor="max-turns">{mode === 'create' ? t('create.maxTurns') : t('detail.maxTurns')}</Label>
        <Input
          id="max-turns"
          type="number"
          min={1}
          max={60000}
          value={maxTurns}
          onChange={(e) => handleFieldChange(setMaxTurns, parseInt(e.target.value) || 60)}
          className="w-24"
          disabled={isProcessing}
        />
        {mode === 'create' && (
          <p className="text-xs text-muted-foreground">{t('create.maxTurnsHelp')}</p>
        )}
      </div>

      {/* Model Selection */}
      {modelProviders.length > 0 && (
        <div className="space-y-2">
          <Label>{t('create.modelLabel')}</Label>
          <ModelSelect
            value={null}
            modelProvider={selectedModelProvider}
            modelName={selectedModelName}
            onChange={(p, m) => {
              handleFieldChange(setSelectedModelProvider, p);
              setSelectedModelName(m);
            }}
            providers={modelProviders}
            placeholder={mode === 'create' ? t('create.modelDefault') : t('detail.modelDefault')}
            disabled={isProcessing}
            aria-label={t('create.modelLabel')}
          />
          <p className="text-xs text-muted-foreground">
            {mode === 'create' ? t('create.modelHelp') : t('detail.modelHelp')}
          </p>
        </div>
      )}

      {/* Executor Selection */}
      {executors.length > 0 && (
        <div className="space-y-2">
          <Label>{t('create.executorLabel')}</Label>
          <ExecutorSelect
            value={selectedExecutorName}
            onChange={(id) => handleFieldChange(setSelectedExecutorName, id)}
            executors={executors}
            placeholder={t('create.executorLocal')}
            disabled={isProcessing}
            aria-label={t('create.executorLabel')}
            showAll
          />
          <p className="text-xs text-muted-foreground">
            {t('create.executorHelp')}
          </p>
        </div>
      )}

      {/* Submit Error */}
      {errors.submit && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="text-sm">{errors.submit}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-4 pt-4 border-t">
        {mode === 'create' ? (
          <Button type="submit" disabled={isProcessing}>
            {isProcessing ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('create.creating')}
              </>
            ) : (
              t('create.createButton')
            )}
          </Button>
        ) : (
          <Button
            type="submit"
            disabled={isProcessing || !hasChanges}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('edit.saving')}
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                {t('detail.saveChanges')}
              </>
            )}
          </Button>
        )}

        {mode === 'edit' && !isSystem && onDelete && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" disabled={isProcessing}>
                {isDeleting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('delete.deleting')}
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    {tc('actions.delete')}
                  </>
                )}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t('delete.title')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t('delete.confirm', { name: presetName || name })} {t('delete.description')}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tc('actions.cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={onDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {tc('actions.delete')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}

        {mode === 'create' && (
          <Button type="button" variant="outline" disabled={isProcessing} onClick={() => window.history.back()}>
            {tc('actions.cancel')}
          </Button>
        )}
      </div>
    </form>
  );
}

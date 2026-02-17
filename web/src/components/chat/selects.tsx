'use client';

import React from 'react';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// ─── Types ───────────────────────────────────────────────

interface ModelProvider {
  name: string;
  models: { key: string; display_name: string }[];
}

interface AgentPreset {
  id: string;
  name: string;
}

interface Executor {
  id: string;
  name: string;
  status?: string;
  gpu_required?: boolean;
}

type SelectSize = 'default' | 'sm' | 'xs';

// ─── ModelSelect ─────────────────────────────────────────

interface ModelSelectProps {
  value: string | null;
  modelProvider: string | null;
  modelName: string | null;
  onChange: (provider: string | null, modelName: string | null) => void;
  providers: ModelProvider[];
  size?: SelectSize;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
  'aria-label'?: string;
}

export const ModelSelect = React.memo(function ModelSelect({
  modelProvider,
  modelName,
  onChange,
  providers,
  size = 'default',
  className,
  disabled,
  placeholder = 'Default (Kimi K2.5)',
  'aria-label': ariaLabel = 'Model',
}: ModelSelectProps) {
  const selectValue = modelProvider && modelName
    ? `${modelProvider}/${modelName}`
    : '__default__';

  const handleChange = (value: string) => {
    if (value === '__default__') {
      onChange(null, null);
    } else {
      const [provider, ...parts] = value.split('/');
      onChange(provider, parts.join('/'));
    }
  };

  return (
    <Select value={selectValue} onValueChange={handleChange} disabled={disabled}>
      <SelectTrigger size={size} className={className} aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__default__">{placeholder}</SelectItem>
        {providers.map((provider) => (
          <SelectGroup key={provider.name}>
            <SelectLabel>
              {provider.name.charAt(0).toUpperCase() + provider.name.slice(1)}
            </SelectLabel>
            {provider.models.map((model) => (
              <SelectItem key={model.key} value={model.key}>
                {model.display_name}
              </SelectItem>
            ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
});

// ─── AgentPresetSelect ───────────────────────────────────

interface AgentPresetSelectProps {
  value: string | null;
  onChange: (presetId: string | null) => void;
  presets: AgentPreset[];
  size?: SelectSize;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
  'aria-label'?: string;
}

export const AgentPresetSelect = React.memo(function AgentPresetSelect({
  value,
  onChange,
  presets,
  size = 'default',
  className,
  disabled,
  placeholder = 'Custom Config',
  'aria-label': ariaLabel = 'Agent',
}: AgentPresetSelectProps) {
  const handleChange = (val: string) => {
    onChange(val === '__custom__' ? null : val);
  };

  return (
    <Select value={value || '__custom__'} onValueChange={handleChange} disabled={disabled}>
      <SelectTrigger size={size} className={className} aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__custom__">{placeholder}</SelectItem>
        {presets.map((preset) => (
          <SelectItem key={preset.id} value={preset.id}>
            {preset.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
});

// ─── ExecutorSelect ──────────────────────────────────────

interface ExecutorSelectProps {
  value: string | null;
  onChange: (executorId: string | null) => void;
  executors: Executor[];
  size?: SelectSize;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
  'aria-label'?: string;
  /** Show all executors (including offline) with status badges */
  showAll?: boolean;
}

export const ExecutorSelect = React.memo(function ExecutorSelect({
  value,
  onChange,
  executors,
  size = 'default',
  className,
  disabled,
  placeholder = 'Local',
  'aria-label': ariaLabel = 'Executor',
  showAll = false,
}: ExecutorSelectProps) {
  const handleChange = (val: string) => {
    onChange(val === '__local__' ? null : val);
  };

  return (
    <Select value={value || '__local__'} onValueChange={handleChange} disabled={disabled}>
      <SelectTrigger size={size} className={className} aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__local__">{placeholder}</SelectItem>
        {executors.map((executor) => (
          <SelectItem
            key={executor.id}
            value={executor.id}
            disabled={!showAll && executor.status !== 'online'}
          >
            {executor.name}
            {executor.status !== 'online' && ` (${executor.status})`}
            {executor.gpu_required && ' [GPU]'}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
});

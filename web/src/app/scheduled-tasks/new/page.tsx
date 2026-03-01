'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { toast } from 'sonner';
import { useCreateScheduledTask } from '@/hooks/use-scheduled-tasks';
import { useAgentPresets } from '@/hooks/use-agents';
import { useChannelBindings } from '@/hooks/use-channels';
import { useTranslation } from '@/i18n/client';

const SCHEDULE_TYPES = [
  { value: 'cron', labelKey: 'scheduleTypes.cron' },
  { value: 'interval', labelKey: 'scheduleTypes.interval' },
  { value: 'once', labelKey: 'scheduleTypes.once' },
] as const;

const CONTEXT_MODES = [
  { value: 'isolated', labelKey: 'contextModes.isolated' },
  { value: 'session', labelKey: 'contextModes.session' },
] as const;

export default function NewScheduledTaskPage() {
  const router = useRouter();
  const { t } = useTranslation('scheduled-tasks');
  const { t: tc } = useTranslation('common');

  const createTask = useCreateScheduledTask();
  const { data: agentsData, isLoading: agentsLoading } = useAgentPresets();
  const { data: channelsData, isLoading: channelsLoading } = useChannelBindings();

  const [name, setName] = useState('');
  const [agentId, setAgentId] = useState('');
  const [prompt, setPrompt] = useState('');
  const [scheduleType, setScheduleType] = useState('');
  const [scheduleValue, setScheduleValue] = useState('');
  const [contextMode, setContextMode] = useState('isolated');
  const [maxRuns, setMaxRuns] = useState('');
  const [channelBindingId, setChannelBindingId] = useState('');

  const agents = agentsData?.presets || [];
  const channels = channelsData?.bindings?.filter((b) => b.enabled && !b.is_global) || [];

  const getPlaceholder = () => {
    switch (scheduleType) {
      case 'cron':
        return t('placeholders.cronValue');
      case 'interval':
        return t('placeholders.intervalValue');
      case 'once':
        return t('placeholders.onceValue');
      default:
        return '';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim() || !agentId || !prompt.trim() || !scheduleType || !scheduleValue.trim()) {
      toast.error(tc('errors.validation'));
      return;
    }

    try {
      await createTask.mutateAsync({
        name: name.trim(),
        agent_id: agentId,
        prompt: prompt.trim(),
        schedule_type: scheduleType,
        schedule_value: scheduleValue.trim(),
        context_mode: contextMode,
        max_runs: maxRuns ? parseInt(maxRuns, 10) : null,
        channel_binding_id: channelBindingId && channelBindingId !== 'none' ? channelBindingId : null,
      });
      toast.success(t('messages.created'));
      router.push('/scheduled-tasks');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8 max-w-2xl">
        {/* Back Link */}
        <Link
          href="/scheduled-tasks"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('title')}
        </Link>

        <Card>
          <CardHeader>
            <CardTitle>{t('create')}</CardTitle>
            <CardDescription>{t('description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Name */}
              <div className="space-y-2">
                <Label htmlFor="name">{t('fields.name')}</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="daily-report"
                  required
                />
              </div>

              {/* Agent */}
              <div className="space-y-2">
                <Label htmlFor="agent">{t('fields.agent')}</Label>
                {agentsLoading ? (
                  <div className="flex items-center gap-2 py-2">
                    <Spinner size="sm" />
                    <span className="text-sm text-muted-foreground">{tc('status.loading')}</span>
                  </div>
                ) : (
                  <Select value={agentId} onValueChange={setAgentId}>
                    <SelectTrigger id="agent">
                      <SelectValue placeholder={t('fields.agent')} />
                    </SelectTrigger>
                    <SelectContent>
                      {agents.map((agent) => (
                        <SelectItem key={agent.id} value={agent.id}>
                          {agent.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              {/* Prompt */}
              <div className="space-y-2">
                <Label htmlFor="prompt">{t('fields.prompt')}</Label>
                <Textarea
                  id="prompt"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Generate a daily summary report..."
                  rows={4}
                  required
                />
              </div>

              {/* Schedule Type */}
              <div className="space-y-2">
                <Label htmlFor="schedule-type">{t('fields.scheduleType')}</Label>
                <Select value={scheduleType} onValueChange={setScheduleType}>
                  <SelectTrigger id="schedule-type">
                    <SelectValue placeholder={t('fields.scheduleType')} />
                  </SelectTrigger>
                  <SelectContent>
                    {SCHEDULE_TYPES.map(({ value, labelKey }) => (
                      <SelectItem key={value} value={value}>
                        {t(labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Schedule Value */}
              <div className="space-y-2">
                <Label htmlFor="schedule-value">{t('fields.scheduleValue')}</Label>
                <Input
                  id="schedule-value"
                  value={scheduleValue}
                  onChange={(e) => setScheduleValue(e.target.value)}
                  placeholder={getPlaceholder()}
                  required
                />
              </div>

              {/* Context Mode */}
              <div className="space-y-2">
                <Label htmlFor="context-mode">{t('fields.contextMode')}</Label>
                <Select value={contextMode} onValueChange={setContextMode}>
                  <SelectTrigger id="context-mode">
                    <SelectValue placeholder={t('fields.contextMode')} />
                  </SelectTrigger>
                  <SelectContent>
                    {CONTEXT_MODES.map(({ value, labelKey }) => (
                      <SelectItem key={value} value={value}>
                        {t(labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Max Runs */}
              <div className="space-y-2">
                <Label htmlFor="max-runs">
                  {t('fields.maxRuns')}
                  <span className="text-muted-foreground text-xs ml-1">({tc('status.optional')})</span>
                </Label>
                <Input
                  id="max-runs"
                  type="number"
                  min={1}
                  value={maxRuns}
                  onChange={(e) => setMaxRuns(e.target.value)}
                  placeholder="100"
                />
              </div>

              {/* Channel Binding */}
              <div className="space-y-2">
                <Label htmlFor="channel-binding">
                  {t('fields.channelBinding')}
                  <span className="text-muted-foreground text-xs ml-1">({tc('status.optional')})</span>
                </Label>
                {channelsLoading ? (
                  <div className="flex items-center gap-2 py-2">
                    <Spinner size="sm" />
                    <span className="text-sm text-muted-foreground">{tc('status.loading')}</span>
                  </div>
                ) : (
                  <Select value={channelBindingId} onValueChange={setChannelBindingId}>
                    <SelectTrigger id="channel-binding">
                      <SelectValue placeholder={t('fields.noChannel')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">{t('fields.noChannel')}</SelectItem>
                      {channels.map((ch) => (
                        <SelectItem key={ch.id} value={ch.id}>
                          [{ch.channel_type}] {ch.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <p className="text-xs text-muted-foreground">{t('hints.channelBinding')}</p>
              </div>

              {/* Submit */}
              <div className="flex justify-end gap-3">
                <Link href="/scheduled-tasks">
                  <Button type="button" variant="outline">
                    {tc('actions.cancel')}
                  </Button>
                </Link>
                <Button type="submit" disabled={createTask.isPending}>
                  {createTask.isPending && <Spinner size="sm" className="mr-2" />}
                  {t('create')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

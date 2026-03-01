'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { useCreateChannelBinding } from '@/hooks/use-channels';
import { useAgentPresets } from '@/hooks/use-agents';
import { useTranslation } from '@/i18n/client';

const CHANNEL_TYPES = [
  { value: 'feishu', labelKey: 'channelTypes.feishu' },
  { value: 'telegram', labelKey: 'channelTypes.telegram' },
  { value: 'webhook', labelKey: 'channelTypes.webhook' },
] as const;

// Credential fields per channel type (stored in binding config)
const CREDENTIAL_FIELDS: Record<string, { key: string; labelKey: string; placeholder: string }[]> = {
  feishu: [
    { key: 'app_id', labelKey: 'fields.appId', placeholder: 'cli_xxxxxxxxxxxx' },
    { key: 'app_secret', labelKey: 'fields.appSecret', placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxx' },
  ],
};

export default function NewChannelBindingPage() {
  const router = useRouter();
  const { t } = useTranslation('channels');
  const { t: tc } = useTranslation('common');

  const createBinding = useCreateChannelBinding();
  const { data: agentsData, isLoading: agentsLoading } = useAgentPresets();

  const [name, setName] = useState('');
  const [channelType, setChannelType] = useState('');
  const [externalId, setExternalId] = useState('');
  const [agentId, setAgentId] = useState('');
  const [triggerPattern, setTriggerPattern] = useState('');
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const agents = agentsData?.presets || [];
  const credentialFields = channelType ? CREDENTIAL_FIELDS[channelType] || [] : [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) { toast.error('Name is required'); return; }
    if (!channelType) { toast.error('Channel type is required'); return; }
    if (!externalId.trim()) { toast.error('External ID is required'); return; }
    if (!agentId) { toast.error('Agent is required'); return; }

    // Validate required credentials for Feishu
    if (channelType === 'feishu') {
      if (!credentials['app_id']?.trim()) { toast.error('App ID is required for Feishu'); return; }
      if (!credentials['app_secret']?.trim()) { toast.error('App Secret is required for Feishu'); return; }
    }

    setSubmitting(true);
    try {
      // Build config from credentials
      const config: Record<string, string> = {};
      for (const field of credentialFields) {
        const value = credentials[field.key];
        if (value && value.trim()) {
          config[field.key] = value.trim();
        }
      }

      await createBinding.mutateAsync({
        name: name.trim(),
        channel_type: channelType,
        external_id: externalId.trim(),
        agent_id: agentId,
        trigger_pattern: triggerPattern.trim() || null,
        config: Object.keys(config).length > 0 ? config : null,
      });

      toast.success(t('messages.created'));
      router.push('/channels');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tc('errors.generic'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1 container px-4 py-8 max-w-2xl">
        {/* Back Link */}
        <Link
          href="/channels"
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
                  placeholder="my-feishu-binding"
                  required
                />
              </div>

              {/* Channel Type */}
              <div className="space-y-2">
                <Label htmlFor="channel-type">{t('fields.channelType')}</Label>
                <Select value={channelType} onValueChange={(v) => {
                  setChannelType(v);
                  setCredentials({});
                }}>
                  <SelectTrigger id="channel-type">
                    <SelectValue placeholder={t('fields.channelType')} />
                  </SelectTrigger>
                  <SelectContent>
                    {CHANNEL_TYPES.map(({ value, labelKey }) => (
                      <SelectItem key={value} value={value}>
                        {t(labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Credential Fields - stored in binding config */}
              {credentialFields.length > 0 && (
                <div className="space-y-4 rounded-lg border p-4 bg-muted/30">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Info className="h-4 w-4 text-blue-500" />
                    {t('credentials.title')}
                  </div>
                  {credentialFields.map((field) => (
                    <div key={field.key} className="space-y-2">
                      <Label htmlFor={field.key}>
                        {t(field.labelKey)}
                      </Label>
                      <Input
                        id={field.key}
                        type={field.key === 'app_secret' ? 'password' : 'text'}
                        value={credentials[field.key] || ''}
                        onChange={(e) => setCredentials((prev) => ({ ...prev, [field.key]: e.target.value }))}
                        placeholder={field.placeholder}
                      />
                    </div>
                  ))}
                  <p className="text-xs text-muted-foreground">
                    {t('credentials.configHint')}
                  </p>
                </div>
              )}

              {/* External ID */}
              <div className="space-y-2">
                <Label htmlFor="external-id">{t('fields.externalId')}</Label>
                <Input
                  id="external-id"
                  value={externalId}
                  onChange={(e) => setExternalId(e.target.value)}
                  placeholder={channelType === 'telegram' ? '123456789' : 'oc_xxxxxxxxxxxx'}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {channelType === 'feishu'
                    ? t('hints.feishuExternalId')
                    : channelType === 'telegram'
                      ? t('hints.telegramExternalId')
                      : t('hints.externalId')
                  }
                </p>
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

              {/* Trigger Pattern */}
              <div className="space-y-2">
                <Label htmlFor="trigger-pattern">
                  {t('fields.triggerPattern')}
                  <span className="text-muted-foreground text-xs ml-1">({tc('status.optional')})</span>
                </Label>
                <Input
                  id="trigger-pattern"
                  value={triggerPattern}
                  onChange={(e) => setTriggerPattern(e.target.value)}
                  placeholder="@bot|/ask"
                />
              </div>

              {/* Submit */}
              <div className="flex justify-end gap-3">
                <Link href="/channels">
                  <Button type="button" variant="outline">
                    {tc('actions.cancel')}
                  </Button>
                </Link>
                <Button type="submit" disabled={submitting}>
                  {submitting && <Spinner size="sm" className="mr-2" />}
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

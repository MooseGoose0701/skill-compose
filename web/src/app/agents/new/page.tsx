'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, FileText, MessageSquare } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useCreateAgentPreset } from '@/hooks/use-agents';
import { AgentBuilderChat } from '@/components/agents/agent-builder-chat';
import { AgentConfigForm, type AgentFormValues } from '@/components/agents/agent-config-form';
import { useTranslation } from '@/i18n/client';

export default function NewAgentPage() {
  const router = useRouter();
  const createPreset = useCreateAgentPreset();
  const { t } = useTranslation('agents');

  const handleSubmit = async (values: AgentFormValues) => {
    const preset = await createPreset.mutateAsync({
      name: values.name,
      description: values.description || undefined,
      system_prompt: values.system_prompt || undefined,
      skill_ids: values.skill_ids.length > 0 ? values.skill_ids : undefined,
      builtin_tools: values.builtin_tools.length > 0 ? values.builtin_tools : undefined,
      mcp_servers: values.mcp_servers.length > 0 ? values.mcp_servers : undefined,
      max_turns: values.max_turns,
      model_provider: values.model_provider || undefined,
      model_name: values.model_name || undefined,
      executor_id: values.executor_id || undefined,
    });
    router.push(`/agents/${preset.id}`);
  };

  return (
    <div className="container mx-auto py-8 max-w-3xl">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/agents"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-4"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('create.backToAgents')}
        </Link>
        <h1 className="text-3xl font-bold">{t('create.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('create.subtitle')}</p>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="chat" className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="chat" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            {t('create.tabChat')}
          </TabsTrigger>
          <TabsTrigger value="form" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {t('create.tabManual')}
          </TabsTrigger>
        </TabsList>

        {/* Chat Mode */}
        <TabsContent value="chat">
          <Card>
            <CardHeader>
              <CardTitle>{t('create.chatTitle')}</CardTitle>
              <CardDescription>{t('create.chatDescription')}</CardDescription>
            </CardHeader>
            <CardContent>
              <AgentBuilderChat />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Form Mode */}
        <TabsContent value="form">
          <Card>
            <CardHeader>
              <CardTitle>{t('create.formTitle')}</CardTitle>
              <CardDescription>{t('create.formDescription')}</CardDescription>
            </CardHeader>
            <CardContent>
              <AgentConfigForm
                mode="create"
                isProcessing={createPreset.isPending}
                onSubmit={handleSubmit}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

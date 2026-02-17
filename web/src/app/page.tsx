'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Bot,
  Sparkles,
  GitBranch,
  Zap,
  Download,
  Plus,
  Archive,
} from 'lucide-react';
import { useTranslation } from '@/i18n/client';
import { useSkills } from '@/hooks/use-skills';
import { useAgentPresets } from '@/hooks/use-agents';
import { useMCPServers } from '@/hooks/use-mcp';
import { useExecutors } from '@/hooks/use-executors';

function StatCard({ value, label, isLoading }: { value: number; label: string; isLoading: boolean }) {
  return (
    <div className="rounded-lg border bg-card p-4 text-card-foreground">
      {isLoading ? (
        <div className="h-8 w-12 animate-pulse rounded bg-muted" />
      ) : (
        <div className="text-2xl font-bold tabular-nums">{value}</div>
      )}
      <div className="mt-1 text-sm text-muted-foreground">{label}</div>
    </div>
  );
}

export default function Home() {
  const { t } = useTranslation('home');
  const { t: tc } = useTranslation('common');

  const { data: skillsData, isLoading: skillsLoading } = useSkills();
  const { data: agentsData, isLoading: agentsLoading } = useAgentPresets();
  const { data: mcpData, isLoading: mcpLoading } = useMCPServers();
  const { data: executorsData, isLoading: executorsLoading } = useExecutors();

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1">
        {/* Hero */}
        <section className="container px-4 pt-12 pb-8 md:pt-16 md:pb-10">
          <div className="mx-auto max-w-3xl">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl leading-[1.15] [text-wrap:balance]">
              {t('title_line1')}<br />
              {t('title_line2')}
            </h1>
            <p className="mt-4 text-lg tracking-wide text-muted-foreground italic sm:text-xl">
              {t('tagline')}
            </p>
            <div className="mt-8 inline-flex flex-col items-center gap-1">
              <Link
                href="/agents/new"
                className="inline-flex items-center justify-center rounded-lg bg-primary px-8 py-3.5 text-base font-semibold text-primary-foreground shadow-sm transition-[transform,box-shadow] hover:shadow-md hover:scale-[1.02] motion-reduce:transform-none"
              >
                {t('cta.main')} <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <span className="text-sm text-muted-foreground">
                {t('cta.subtext')}
              </span>
            </div>
          </div>
        </section>

        {/* Stats */}
        <section className="container px-4 pb-8">
          <div className="mx-auto max-w-3xl">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard value={skillsData?.total ?? 0} label={t('stats.skills')} isLoading={skillsLoading} />
              <StatCard value={agentsData?.total ?? 0} label={t('stats.agents')} isLoading={agentsLoading} />
              <StatCard value={mcpData?.count ?? 0} label={t('stats.mcpServers')} isLoading={mcpLoading} />
              <StatCard value={executorsData?.total ?? 0} label={t('stats.executors')} isLoading={executorsLoading} />
            </div>
          </div>
        </section>

        {/* Quick Actions */}
        <section className="container px-4 pb-10">
          <div className="mx-auto max-w-3xl">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Link
                href="/skills"
                className="group flex items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-accent"
              >
                <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors" />
                <div>
                  <div className="font-medium">{t('quickActions.browseSkills.title')}</div>
                  <div className="text-sm text-muted-foreground">{t('quickActions.browseSkills.description')}</div>
                </div>
              </Link>
              <Link
                href="/skills/new"
                className="group flex items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-accent"
              >
                <Plus className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors" />
                <div>
                  <div className="font-medium">{t('quickActions.createSkill.title')}</div>
                  <div className="text-sm text-muted-foreground">{t('quickActions.createSkill.description')}</div>
                </div>
              </Link>
              <Link
                href="/import"
                className="group flex items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-accent"
              >
                <Download className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors" />
                <div>
                  <div className="font-medium">{t('quickActions.importSkill.title')}</div>
                  <div className="text-sm text-muted-foreground">{t('quickActions.importSkill.description')}</div>
                </div>
              </Link>
              <Link
                href="/skills/evolve"
                className="group flex items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-accent"
              >
                <Zap className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground group-hover:text-foreground transition-colors" />
                <div>
                  <div className="font-medium">{t('quickActions.evolveSkills.title')}</div>
                  <div className="text-sm text-muted-foreground">{t('quickActions.evolveSkills.description')}</div>
                </div>
              </Link>
            </div>
          </div>
        </section>

        {/* Features */}
        <section className="container px-4 py-16 border-t">
          <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">{t('featureCards.conversational.title')}</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('featureCards.conversational.description')}
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <GitBranch className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">{t('featureCards.autoGenerated.title')}</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('featureCards.autoGenerated.description')}
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">{t('featureCards.evolution.title')}</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('featureCards.evolution.description')}
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <Archive className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">{t('featureCards.backup.title')}</h3>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {t('featureCards.backup.description')}
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

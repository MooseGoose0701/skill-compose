'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  ArrowRight,
  Plus,
  Wrench,
  Plug,
  Bot,
  History,
  Sparkles,
  GitBranch,
  Zap,
  Folder,
  Terminal,
  Container,
  Archive,
  TerminalSquare,
  ChevronDown,
  Download,
  MessageSquare,
} from 'lucide-react';
import { useTranslation } from '@/i18n/client';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu';
export default function Home() {
  const { t } = useTranslation('home');
  const { t: tc } = useTranslation('common');
  const router = useRouter();

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero */}
      <main className="flex-1">
        <section className="container px-4 py-12 md:py-16">
          <div className="mx-auto max-w-3xl">
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl leading-[1.15]">
              {t('title_line1')}<br />
              {t('title_line2')}
            </h1>
            <p className="mt-4 text-lg tracking-wide text-muted-foreground italic sm:text-xl">
              {t('tagline')}
            </p>
            <div className="mt-10 mb-12 inline-flex flex-col items-center gap-1">
              <Link
                href="/agents/new"
                className="inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-blue-500 to-blue-300 px-10 py-4 text-lg font-semibold text-white shadow-lg transition-all hover:shadow-xl hover:scale-[1.02]"
              >
                {t('cta.main')} <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
              <span className="text-sm text-muted-foreground">
                {t('cta.subtext')}
              </span>
            </div>
            <div className="flex flex-col items-stretch gap-4 text-center w-full">
              {/* Primary Actions - 4 equal width buttons */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                <Link
                  href="/agents"
                  className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
                >
                  <Bot className="mr-2 h-4 w-4" />
                  {tc('actions.view')} {tc('nav.agents')}
                </Link>
                <Link
                  href="/skills"
                  className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
                >
                  <ArrowRight className="mr-2 h-4 w-4" />
                  {tc('actions.view')} {tc('nav.skills')}
                </Link>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      {tc('actions.add')} {tc('nav.skills')}
                      <ChevronDown className="ml-2 h-3 w-3 opacity-70" />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="center">
                    <DropdownMenuItem onSelect={() => router.push('/skills/new')}>
                      <Sparkles className="mr-2 h-4 w-4" />
                      {tc('actions.create')}
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => router.push('/import')}>
                      <Download className="mr-2 h-4 w-4" />
                      {tc('actions.import')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                <Link
                  href="/skills/evolve"
                  className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
                >
                  <Zap className="mr-2 h-4 w-4" />
                  {t('cta.evolve')}
                </Link>
              </div>
              {/* Secondary Navigation - Executors, Tools, MCP, Traces, Sessions */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                <Link
                  href="/executors"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Container className="mr-2 h-4 w-4" />
                  {tc('nav.executors')}
                </Link>
                <Link
                  href="/tools"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Wrench className="mr-2 h-4 w-4" />
                  {tc('nav.tools')}
                </Link>
                <Link
                  href="/mcp"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Plug className="mr-2 h-4 w-4" />
                  {tc('nav.mcp')}
                </Link>
                <Link
                  href="/traces"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <History className="mr-2 h-4 w-4" />
                  {tc('nav.traces')}
                </Link>
                <Link
                  href="/sessions"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <MessageSquare className="mr-2 h-4 w-4" />
                  {tc('nav.sessions')}
                </Link>
              </div>
              {/* Tertiary Navigation - Files, Terminal, Settings, Backup */}
              <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-4 gap-3">
                <Link
                  href="/files"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Folder className="mr-2 h-4 w-4" />
                  {tc('nav.files')}
                </Link>
                <Link
                  href="/terminal"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <TerminalSquare className="mr-2 h-4 w-4" />
                  {tc('nav.terminal')}
                </Link>
                <Link
                  href="/environment"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Terminal className="mr-2 h-4 w-4" />
                  {tc('nav.environment')}
                </Link>
                <Link
                  href="/backup"
                  className="inline-flex items-center justify-center rounded-md border border-input bg-background px-6 py-2.5 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Archive className="mr-2 h-4 w-4" />
                  {tc('nav.backup')}
                </Link>
              </div>
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

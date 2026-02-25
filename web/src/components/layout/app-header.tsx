'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import {
  Sun,
  Moon,
  BookOpen,
  Settings,
  Container,
  Folder,
  Terminal,
  Archive,
  MessageSquare,
  Activity,
  Users,
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LanguageSwitcher } from './language-switcher';
import { UserMenu } from './user-menu';
import { NavLink } from './nav-link';
import { useTranslation } from '@/i18n/client';

const MORE_MONITOR_ITEMS = [
  { href: '/traces', icon: Activity, labelKey: 'nav.traces' },
  { href: '/sessions', icon: MessageSquare, labelKey: 'nav.sessions' },
];

const MORE_SYSTEM_ITEMS = [
  { href: '/executors', icon: Container, labelKey: 'nav.executors' },
  { href: '/files', icon: Folder, labelKey: 'nav.files' },
  { href: '/environment', icon: Terminal, labelKey: 'nav.environment' },
  { href: '/accounts', icon: Users, labelKey: 'nav.accounts' },
  { href: '/backup', icon: Archive, labelKey: 'nav.backup' },
];

export function AppHeader() {
  const { theme, setTheme } = useTheme();
  const { t } = useTranslation('common');
  const router = useRouter();

  return (
    <header className="border-b">
      <div className="container flex h-14 items-center px-4">
        {/* Left: Logo + Brand + Primary Nav */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/logo.png" alt="Skill Compose" width={28} height={28} />
            <span className="text-sm font-semibold hidden sm:inline">Skill Compose</span>
          </Link>

          <nav className="flex items-center gap-4">
            <NavLink href="/agents">{t('nav.agents')}</NavLink>
            <NavLink href="/skills">{t('nav.skills')}</NavLink>
            <NavLink href="/tools">{t('nav.tools')}</NavLink>
            <NavLink href="/mcp">{t('nav.mcp')}</NavLink>
          </nav>
        </div>

        {/* Right: More dropdown + Docs + Language + Theme */}
        <TooltipProvider delayDuration={300}>
          <div className="ml-auto flex items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label={t('nav.more')}>
                  <Settings className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel className="text-xs text-muted-foreground font-normal uppercase tracking-wider">
                  {t('nav.groupMonitor')}
                </DropdownMenuLabel>
                {MORE_MONITOR_ITEMS.map((item) => (
                  <DropdownMenuItem
                    key={item.href}
                    onClick={() => router.push(item.href)}
                  >
                    <item.icon className="mr-2 h-4 w-4" />
                    {t(item.labelKey)}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuLabel className="text-xs text-muted-foreground font-normal uppercase tracking-wider">
                  {t('nav.groupSystem')}
                </DropdownMenuLabel>
                {MORE_SYSTEM_ITEMS.map((item) => (
                  <DropdownMenuItem
                    key={item.href}
                    onClick={() => router.push(item.href)}
                  >
                    <item.icon className="mr-2 h-4 w-4" />
                    {t(item.labelKey)}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            <Tooltip>
              <TooltipTrigger asChild>
                <a
                  href={process.env.NEXT_PUBLIC_DOCS_URL || 'http://localhost:62630'}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button variant="ghost" size="icon" aria-label={t('tooltips.documentation')}>
                    <BookOpen className="h-4 w-4" />
                  </Button>
                </a>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t('tooltips.documentation')}</p>
              </TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <a
                  href="https://discord.gg/8QK5suCV9m"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Button variant="ghost" size="icon" aria-label={t('tooltips.discord')}>
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.947 2.418-2.157 2.418z" />
                    </svg>
                  </Button>
                </a>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t('tooltips.discord')}</p>
              </TooltipContent>
            </Tooltip>

            <LanguageSwitcher />

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                  aria-label={t('tooltips.toggleTheme')}
                  className="relative"
                >
                  <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
                  <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t('tooltips.toggleTheme')}</p>
              </TooltipContent>
            </Tooltip>

            <UserMenu />
          </div>
        </TooltipProvider>
      </div>
    </header>
  );
}

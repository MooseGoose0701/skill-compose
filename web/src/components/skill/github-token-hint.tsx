'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { KeyRound, X } from 'lucide-react';
import { useTranslation } from '@/i18n/client';
import { settingsApi } from '@/lib/api';

const STORAGE_KEY = 'skills:github-token-hint-dismissed';

export function GithubTokenHint() {
  const { t } = useTranslation('skills');
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Already dismissed by user — skip API call
    if (localStorage.getItem(STORAGE_KEY)) return;

    // Check if GITHUB_TOKEN is already configured
    settingsApi.getEnv().then((res) => {
      const token = res.variables.find((v) => v.key === 'GITHUB_TOKEN');
      if (!token || !token.value) {
        setVisible(true);
      }
    }).catch(() => {
      // API error — show hint as fallback
      setVisible(true);
    });
  }, []);

  if (!visible) return null;

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(STORAGE_KEY, '1');
  };

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800/60 dark:bg-amber-950/30 p-3.5 flex items-center justify-between gap-4 mb-6">
      <div className="flex items-start gap-3 min-w-0">
        <KeyRound className="h-4 w-4 mt-0.5 text-amber-600 dark:text-amber-400 shrink-0" />
        <p className="text-sm text-amber-800 dark:text-amber-200">
          {t('list.githubTokenHint')}{' '}
          <Link
            href="/environment"
            className="underline underline-offset-2 font-medium hover:text-amber-900 dark:hover:text-amber-100"
          >
            {t('list.githubTokenHintLink')}
          </Link>
        </p>
      </div>
      <button
        onClick={dismiss}
        className="text-amber-600 dark:text-amber-400 hover:text-amber-800 dark:hover:text-amber-200 shrink-0"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

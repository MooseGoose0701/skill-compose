'use client';

import { usePathname } from 'next/navigation';
import { AppHeader } from './app-header';

export function ConditionalHeader() {
  const pathname = usePathname();

  // Hide header on published agent pages, fullscreen chat, and login
  if (pathname.startsWith('/published/') || pathname === '/chat' || pathname === '/login') {
    return null;
  }

  return <AppHeader />;
}

'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { useState } from 'react';
import { ChatProvider } from '@/components/chat/chat-provider';
import { AuthGuard } from '@/components/auth/auth-guard';
// i18next is initialized synchronously on import — no useEffect needed
import '@/i18n/client';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        <AuthGuard>
          <ChatProvider>
            {children}
          </ChatProvider>
        </AuthGuard>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

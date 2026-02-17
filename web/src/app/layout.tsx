import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { cookies } from 'next/headers';
import './globals.css';
import { Providers } from './providers';
import { Toaster } from 'sonner';
import { ConditionalHeader } from '@/components/layout/conditional-header';
import { cookieName, fallbackLng, languages, Language } from '@/i18n/settings';

export const metadata: Metadata = {
  title: 'Skill Compose',
  description: 'Describe your agent. We\'ll build it — and the skills it needs.',
  icons: {
    icon: '/logo.png',
    apple: '/logo.png',
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const langCookie = cookieStore.get(cookieName)?.value;
  const lang = langCookie && languages.includes(langCookie as Language)
    ? langCookie
    : fallbackLng;

  return (
    <html lang={lang} suppressHydrationWarning>
      <body className={GeistSans.className}>
        <Providers>
          <div className="min-h-screen bg-background">
            <ConditionalHeader />
            {children}
          </div>
          <Toaster richColors position="top-right" />
        </Providers>
      </body>
    </html>
  );
}

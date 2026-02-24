'use client';

import { useEffect, useState, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { authApi } from '@/lib/api';
import { Spinner } from '@/components/ui/spinner';

const PUBLIC_ROUTES = ['/login', '/published'];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, refreshToken, updateAccessToken, logout } = useAuthStore();
  const [initialCheckDone, setInitialCheckDone] = useState(false);
  const authEnabledRef = useRef<boolean | null>(null);
  const hasValidatedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      // Check if route is public
      if (PUBLIC_ROUTES.some((r) => pathname.startsWith(r))) {
        if (!cancelled) setInitialCheckDone(true);
        return;
      }

      // If we've already validated auth and user is still authenticated, skip re-check
      if (hasValidatedRef.current && isAuthenticated && authEnabledRef.current !== null) {
        if (!cancelled) setInitialCheckDone(true);
        return;
      }

      // Check server auth status (only if not cached)
      try {
        if (authEnabledRef.current === null) {
          const status = await authApi.status();
          if (!cancelled) {
            authEnabledRef.current = status.auth_enabled;
          }
        }

        if (!authEnabledRef.current) {
          // Auth disabled on server, render children directly
          if (!cancelled) setInitialCheckDone(true);
          return;
        }

        // Auth is enabled — check if user has valid token
        if (!isAuthenticated) {
          router.replace('/login');
          return;
        }

        // Try to validate token by calling /auth/me (only on initial check)
        if (!hasValidatedRef.current) {
          try {
            await authApi.getMe();
            hasValidatedRef.current = true;
            if (!cancelled) setInitialCheckDone(true);
          } catch {
            // Token might be expired, try refresh
            if (refreshToken) {
              try {
                const result = await authApi.refresh(refreshToken);
                updateAccessToken(result.access_token);
                hasValidatedRef.current = true;
                if (!cancelled) setInitialCheckDone(true);
              } catch {
                logout();
                router.replace('/login');
              }
            } else {
              logout();
              router.replace('/login');
            }
          }
        } else {
          if (!cancelled) setInitialCheckDone(true);
        }
      } catch {
        // Can't reach server — allow through but don't cache the result
        // so the next navigation will re-check
        if (!cancelled) {
          setInitialCheckDone(true);
        }
      }
    }

    checkAuth();

    return () => {
      cancelled = true;
    };
  }, [pathname, isAuthenticated, refreshToken, router, updateAccessToken, logout]);

  // Reset validation when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      hasValidatedRef.current = false;
    }
  }, [isAuthenticated]);

  // Public routes render immediately
  if (PUBLIC_ROUTES.some((r) => pathname.startsWith(r))) {
    return <>{children}</>;
  }

  // If auth disabled, render immediately
  if (authEnabledRef.current === false) {
    return <>{children}</>;
  }

  // Still doing initial check
  if (!initialCheckDone) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  return <>{children}</>;
}

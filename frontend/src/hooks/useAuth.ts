'use client';

import { useSession, signIn, signOut, SessionProvider } from 'next-auth/react';
import { useCallback } from 'react';

export { SessionProvider as AuthProvider };

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export function useAuth() {
  const { data: session, status } = useSession();

  const isLoading = status === 'loading';
  const isAuthenticated = status === 'authenticated';
  const user = session?.user ?? null;

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        throw new Error(
          result.error === 'CredentialsSignin'
            ? 'Invalid email or password'
            : result.error
        );
      }

      return result;
    },
    []
  );

  const logout = useCallback(async () => {
    await signOut({ callbackUrl: '/login' });
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      const response = await fetch(`${BACKEND_URL}/api/v1/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Registration failed');
      }

      // Auto-login after registration
      return login(email, password);
    },
    [login]
  );

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    register,
  };
}

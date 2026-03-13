'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { createElement } from 'react';
import { login as apiLogin, register as apiRegister } from '@/lib/api';
import type { User, AuthTokens } from '@/types/user';

interface AuthContextValue {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKENS_KEY = 'kalye_tokens';
const USER_KEY = 'kalye_user';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    try {
      const storedTokens = localStorage.getItem(TOKENS_KEY);
      const storedUser = localStorage.getItem(USER_KEY);
      if (storedTokens) {
        setTokens(JSON.parse(storedTokens));
      }
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
    } catch {
      // Invalid stored data
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const authTokens = await apiLogin(email, password);
    setTokens(authTokens);
    localStorage.setItem(TOKENS_KEY, JSON.stringify(authTokens));
    // Set cookie so Next.js middleware can verify auth on server side
    document.cookie = `kalye_auth=${authTokens.access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
  }, []);

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      const authTokens = await apiRegister(name, email, password);
      setTokens(authTokens);
      localStorage.setItem(TOKENS_KEY, JSON.stringify(authTokens));
      document.cookie = `kalye_auth=${authTokens.access_token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
    },
    []
  );

  const logout = useCallback(() => {
    setUser(null);
    setTokens(null);
    localStorage.removeItem(TOKENS_KEY);
    localStorage.removeItem(USER_KEY);
    document.cookie = 'kalye_auth=; path=/; max-age=0';
    window.location.href = '/login';
  }, []);

  const value: AuthContextValue = {
    user,
    tokens,
    isAuthenticated: tokens !== null,
    isLoading,
    login,
    register,
    logout,
  };

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

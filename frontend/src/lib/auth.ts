import type { NextAuthOptions, DefaultSession } from 'next-auth';
import type { JWT } from 'next-auth/jwt';
import CredentialsProvider from 'next-auth/providers/credentials';
import { getServerSession as nextAuthGetServerSession } from 'next-auth';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
  accessToken: string;
}

declare module 'next-auth' {
  interface Session extends DefaultSession {
    user: {
      id: string;
      email: string;
      name: string;
      role: string;
      accessToken: string;
    };
  }

  interface User {
    id: string;
    email: string;
    name: string;
    role: string;
    accessToken: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    id: string;
    email: string;
    role: string;
    accessToken: string;
  }
}

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'Credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error('Email and password are required');
        }

        try {
          const response = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });

          if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || 'Invalid credentials');
          }

          const data = await response.json();

          return {
            id: data.user.id,
            email: data.user.email,
            name: data.user.name || data.user.email,
            role: data.user.role || 'user',
            accessToken: data.access_token,
          };
        } catch (error) {
          if (error instanceof Error) {
            throw error;
          }
          throw new Error('Authentication failed');
        }
      },
    }),
  ],
  session: {
    strategy: 'jwt',
    maxAge: 24 * 60 * 60, // 24 hours
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.role = user.role;
        token.accessToken = user.accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.user = {
        id: token.id,
        email: token.email,
        name: token.name || token.email,
        role: token.role,
        accessToken: token.accessToken,
      };
      return session;
    },
  },
};

export async function getServerAuthSession() {
  return nextAuthGetServerSession(authOptions);
}

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";

import type { AuthSession } from "@/lib/auth";

const AUTH_STORAGE_KEY = "empulse-auth-session";

interface AuthContextValue {
  session: AuthSession | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signUp: (payload: {
    name: string;
    email: string;
    company?: string;
  }) => void;
  login: (payload: { email: string; name?: string }) => void;
  completeOnboarding: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadSession(): AuthSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuthSession) : null;
  } catch {
    return null;
  }
}

function persistSession(session: AuthSession | null) {
  if (session) {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  } else {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<AuthSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setSession(loadSession());
    setIsLoading(false);
  }, []);

  const signUp = useCallback(
    (payload: { name: string; email: string; company?: string }) => {
      const nextSession: AuthSession = {
        email: payload.email,
        name: payload.name,
        company: payload.company ?? "Acme Company",
        isNewUser: true,
        onboarded: false,
        loggedInAt: new Date().toISOString(),
      };
      setSession(nextSession);
      persistSession(nextSession);
      router.push("/onboarding");
    },
    [router],
  );

  const login = useCallback(
    (payload: { email: string; name?: string }) => {
      const existing = loadSession();
      const nextSession: AuthSession = {
        email: payload.email,
        name: payload.name ?? existing?.name ?? "Manager",
        company: existing?.company ?? "Acme Company",
        isNewUser: false,
        onboarded: true,
        loggedInAt: new Date().toISOString(),
      };
      setSession(nextSession);
      persistSession(nextSession);
      router.push("/dashboard");
    },
    [router],
  );

  const completeOnboarding = useCallback(() => {
    setSession((prev) => {
      if (!prev) return prev;
      const next = { ...prev, isNewUser: false, onboarded: true };
      persistSession(next);
      return next;
    });
  }, []);

  const logout = useCallback(() => {
    setSession(null);
    persistSession(null);
    router.push("/");
  }, [router]);

  const value = useMemo(
    () => ({
      session,
      isAuthenticated: Boolean(session),
      isLoading,
      signUp,
      login,
      completeOnboarding,
      logout,
    }),
    [session, isLoading, signUp, login, completeOnboarding, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

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

import {
  completeOnboardingSession,
  fetchCurrentSession,
  fetchLinkedTenants,
  loginWithPassword,
  logoutSession,
  sessionFromAuthState,
  signUpWithPassword,
  switchActiveTenant,
  type ActiveTenant,
  type AuthSession,
  type AuthStatus,
  type AuthUser,
  type TenantMembership,
} from "@/lib/auth";

interface AuthContextValue {
  authStatus: AuthStatus;
  user: AuthUser | null;
  activeTenant: ActiveTenant | null;
  linkedTenants: TenantMembership[];
  accessToken: string | null;
  /** Derived session shape for legacy consumers */
  session: AuthSession | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signUp: (payload: {
    name: string;
    email: string;
    password: string;
    company?: string;
  }) => Promise<void>;
  login: (payload: { email: string; password: string }) => Promise<void>;
  completeOnboarding: () => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  switchTenant: (tenantId: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [authStatus, setAuthStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [activeTenant, setActiveTenant] = useState<ActiveTenant | null>(null);
  const [linkedTenants, setLinkedTenants] = useState<TenantMembership[]>([]);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isNewUser, setIsNewUser] = useState(false);

  const loadLinkedTenants = useCallback(async () => {
    try {
      const tenants = await fetchLinkedTenants();
      setLinkedTenants(tenants);
    } catch {
      setLinkedTenants([]);
    }
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      const current = await fetchCurrentSession();
      if (!current) {
        setUser(null);
        setActiveTenant(null);
        setAccessToken(null);
        setLinkedTenants([]);
        setAuthStatus("unauthenticated");
        return;
      }
      setUser(current.user);
      setActiveTenant(current.activeTenant);
      setAccessToken(current.accessToken);
      setAuthStatus("authenticated");
      await loadLinkedTenants();
    } catch {
      setUser(null);
      setActiveTenant(null);
      setAccessToken(null);
      setLinkedTenants([]);
      setAuthStatus("unauthenticated");
    }
  }, [loadLinkedTenants]);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  const signUp = useCallback(
    async (payload: {
      name: string;
      email: string;
      password: string;
      company?: string;
    }) => {
      const result = await signUpWithPassword({
        name: payload.name,
        email: payload.email,
        password: payload.password,
        company: payload.company ?? "My Company",
      });
      setUser(result.user);
      setActiveTenant(result.activeTenant);
      setAccessToken(result.accessToken);
      setIsNewUser(result.isNewUser);
      setAuthStatus("authenticated");
      await loadLinkedTenants();
      router.push("/onboarding");
    },
    [router, loadLinkedTenants],
  );

  const login = useCallback(
    async (payload: { email: string; password: string }) => {
      const result = await loginWithPassword(payload);
      setUser(result.user);
      setActiveTenant(result.activeTenant);
      setAccessToken(result.accessToken);
      setIsNewUser(result.isNewUser);
      setAuthStatus("authenticated");
      await loadLinkedTenants();
      router.push(result.user.onboarded ? "/dashboard" : "/onboarding");
    },
    [router, loadLinkedTenants],
  );

  const completeOnboarding = useCallback(async () => {
    const result = await completeOnboardingSession();
    setUser(result.user);
    setActiveTenant(result.activeTenant);
    setAccessToken(result.accessToken);
    setIsNewUser(false);
  }, []);

  const logout = useCallback(async () => {
    await logoutSession();
    setUser(null);
    setActiveTenant(null);
    setAccessToken(null);
    setLinkedTenants([]);
    setAuthStatus("unauthenticated");
    router.push("/");
  }, [router]);

  const switchTenant = useCallback(
    async (tenantId: string) => {
      const result = await switchActiveTenant(tenantId);
      setUser(result.user);
      setActiveTenant(result.activeTenant);
      setAccessToken(result.accessToken);
      await loadLinkedTenants();
      router.refresh();
    },
    [loadLinkedTenants, router],
  );

  const session = useMemo(
    () =>
      user && activeTenant
        ? sessionFromAuthState(user, activeTenant, isNewUser)
        : null,
    [user, activeTenant, isNewUser],
  );

  const value = useMemo(
    () => ({
      authStatus,
      user,
      activeTenant,
      linkedTenants,
      accessToken,
      session,
      isAuthenticated: authStatus === "authenticated",
      isLoading: authStatus === "loading",
      signUp,
      login,
      completeOnboarding,
      logout,
      refreshSession,
      switchTenant,
    }),
    [
      authStatus,
      user,
      activeTenant,
      linkedTenants,
      accessToken,
      session,
      signUp,
      login,
      completeOnboarding,
      logout,
      refreshSession,
      switchTenant,
    ],
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

import {
  API_BASE,
  apiFetch,
  clearAuthCredentials,
  setAuthCredentials,
} from "./api-client";
import { throwIfAuthUnavailable } from "./connectivity";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  onboarded: boolean;
  oauthProvider?: string | null;
}

export interface ActiveTenant {
  id: string;
  companyName: string;
  slug: string;
  workspaceSetupComplete: boolean;
}

export interface TenantMembership extends ActiveTenant {
  isActive: boolean;
}

/** @deprecated Use `user` + `activeTenant` from useAuth instead. */
export interface AuthSession {
  userId: string;
  email: string;
  name: string;
  company: string;
  tenantId: string;
  tenantSlug: string;
  isNewUser: boolean;
  onboarded: boolean;
  loggedInAt: string;
  oauthProvider?: string | null;
}

export interface AuthUserResponse {
  id: string;
  email: string;
  name: string;
  tenant_id: string;
  company_name: string;
  tenant_slug: string;
  onboarded: boolean;
  oauth_provider: string | null;
  workspace_setup_complete: boolean;
  created_at: string;
}

export interface SessionApiResponse {
  user: AuthUserResponse;
  access_token: string;
}

export interface AuthApiResponse extends SessionApiResponse {
  is_new_user: boolean;
}

export interface TenantMembershipResponse {
  id: string;
  company_name: string;
  slug: string;
  is_active: boolean;
}

async function parseAuthError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => null);
  return typeof body?.detail === "string" ? body.detail : `${fallback} (${response.status})`;
}

export function userResponseToAuthUser(user: AuthUserResponse): AuthUser {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    onboarded: user.onboarded,
    oauthProvider: user.oauth_provider,
  };
}

export function userResponseToTenant(user: AuthUserResponse): ActiveTenant {
  return {
    id: user.tenant_id,
    companyName: user.company_name,
    slug: user.tenant_slug,
    workspaceSetupComplete: user.workspace_setup_complete,
  };
}

export function onboardingPathForTenant(
  tenant: ActiveTenant | null | undefined,
): string {
  if (tenant && !tenant.workspaceSetupComplete) {
    return "/onboarding/workspace";
  }
  return "/onboarding";
}

export function applySessionCredentials(
  user: AuthUserResponse,
  accessToken: string,
): { user: AuthUser; activeTenant: ActiveTenant } {
  setAuthCredentials(accessToken, user.tenant_id);
  return {
    user: userResponseToAuthUser(user),
    activeTenant: userResponseToTenant(user),
  };
}

export function userToSession(
  user: AuthUserResponse,
  isNewUser: boolean,
): AuthSession {
  return {
    userId: user.id,
    email: user.email,
    name: user.name,
    company: user.company_name,
    tenantId: user.tenant_id,
    tenantSlug: user.tenant_slug,
    isNewUser,
    onboarded: user.onboarded,
    loggedInAt: new Date().toISOString(),
    oauthProvider: user.oauth_provider,
  };
}

export function sessionFromAuthState(
  user: AuthUser,
  activeTenant: ActiveTenant,
  isNewUser = false,
): AuthSession {
  return {
    userId: user.id,
    email: user.email,
    name: user.name,
    company: activeTenant.companyName,
    tenantId: activeTenant.id,
    tenantSlug: activeTenant.slug,
    isNewUser,
    onboarded: user.onboarded,
    loggedInAt: new Date().toISOString(),
    oauthProvider: user.oauthProvider,
  };
}

export async function fetchAuthProviders(): Promise<{
  google: boolean;
  github: boolean;
} | null> {
  try {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 5_000);
    const response = await fetch(`${API_BASE}/api/auth/providers`, {
      cache: "no-store",
      credentials: "include",
      signal: controller.signal,
    });
    window.clearTimeout(timeoutId);
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch {
    return null;
  }
}

export async function fetchCurrentSession(): Promise<{
  user: AuthUser;
  activeTenant: ActiveTenant;
  accessToken: string;
} | null> {
  const response = await apiFetch(`${API_BASE}/api/auth/me`, {
    cache: "no-store",
    timeoutMs: 8_000,
    skipErrorToast: true,
  });
  if (response.status === 401) {
    clearAuthCredentials();
    return null;
  }
  if (!response.ok) {
    throw new Error(await parseAuthError(response, "Failed to load session"));
  }
  const data = (await response.json()) as SessionApiResponse;
  const applied = applySessionCredentials(data.user, data.access_token);
  return { ...applied, accessToken: data.access_token };
}

/** @deprecated Use fetchCurrentSession */
export async function fetchCurrentUser(): Promise<AuthSession | null> {
  const session = await fetchCurrentSession();
  if (!session) return null;
  return sessionFromAuthState(session.user, session.activeTenant);
}

export async function fetchLinkedTenants(): Promise<TenantMembership[]> {
  const response = await apiFetch(`${API_BASE}/api/auth/tenants`, {
    cache: "no-store",
    timeoutMs: 8_000,
    skipErrorToast: true,
  });
  if (!response.ok) {
    throw new Error(await parseAuthError(response, "Failed to load tenants"));
  }
  const rows = (await response.json()) as TenantMembershipResponse[];
  return rows.map((row) => ({
    id: row.id,
    companyName: row.company_name,
    slug: row.slug,
    workspaceSetupComplete: true,
    isActive: row.is_active,
  }));
}

export async function signUpWithPassword(payload: {
  name: string;
  email: string;
  password: string;
  company?: string;
}): Promise<{
  user: AuthUser;
  activeTenant: ActiveTenant;
  isNewUser: boolean;
  accessToken: string;
}> {
  const body: Record<string, string> = {
    name: payload.name,
    email: payload.email,
    password: payload.password,
  };
  if (payload.company?.trim()) {
    body.company = payload.company.trim();
  }
  const response = await apiFetch(`${API_BASE}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    skipErrorToast: true,
  });
  if (!response.ok) {
    await throwIfAuthUnavailable(response, "Sign up failed");
  }
  const data = (await response.json()) as AuthApiResponse;
  const applied = applySessionCredentials(data.user, data.access_token);
  return { ...applied, isNewUser: data.is_new_user, accessToken: data.access_token };
}

export async function loginWithPassword(payload: {
  email: string;
  password: string;
}): Promise<{
  user: AuthUser;
  activeTenant: ActiveTenant;
  isNewUser: boolean;
  accessToken: string;
}> {
  const response = await apiFetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    skipErrorToast: true,
  });
  if (!response.ok) {
    await throwIfAuthUnavailable(response, "Login failed");
  }
  const data = (await response.json()) as AuthApiResponse;
  const applied = applySessionCredentials(data.user, data.access_token);
  return { ...applied, isNewUser: data.is_new_user, accessToken: data.access_token };
}

export async function logoutSession(): Promise<void> {
  await apiFetch(`${API_BASE}/api/auth/logout`, { method: "POST" });
  clearAuthCredentials();
}

export async function completeOnboardingSession(): Promise<{
  user: AuthUser;
  activeTenant: ActiveTenant;
  accessToken: string;
}> {
  const response = await apiFetch(`${API_BASE}/api/auth/onboarding/complete`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseAuthError(response, "Failed to complete onboarding"));
  }
  const data = (await response.json()) as SessionApiResponse;
  const applied = applySessionCredentials(data.user, data.access_token);
  return { ...applied, accessToken: data.access_token };
}

export async function updateWorkspaceName(companyName: string): Promise<{
  user: AuthUser;
  activeTenant: ActiveTenant;
  accessToken: string;
}> {
  const response = await apiFetch(`${API_BASE}/api/auth/workspace`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name: companyName }),
    skipErrorToast: true,
  });
  if (!response.ok) {
    throw new Error(await parseAuthError(response, "Failed to update workspace"));
  }
  const data = (await response.json()) as SessionApiResponse;
  const applied = applySessionCredentials(data.user, data.access_token);
  return { ...applied, accessToken: data.access_token };
}

export async function switchActiveTenant(tenantId: string): Promise<{
  user: AuthUser;
  activeTenant: ActiveTenant;
  accessToken: string;
}> {
  const response = await apiFetch(`${API_BASE}/api/auth/switch-tenant/${tenantId}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseAuthError(response, "Failed to switch tenant"));
  }
  const data = (await response.json()) as SessionApiResponse;
  const applied = applySessionCredentials(data.user, data.access_token);
  return { ...applied, accessToken: data.access_token };
}

export function oauthLoginUrl(
  provider: "google" | "github",
  nextPath: string,
): string {
  const params = new URLSearchParams({ next: nextPath });
  return `${API_BASE}/api/auth/oauth/${provider}?${params.toString()}`;
}

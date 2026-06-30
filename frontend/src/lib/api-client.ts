/**
 * Centralized API client with auth + tenant header injection.
 */

const TOKEN_STORAGE_KEY = "empulse_access_token";
const TENANT_STORAGE_KEY = "empulse_active_tenant_id";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let memoryAccessToken: string | null = null;
let memoryTenantId: string | null = null;

export function setAuthCredentials(token: string | null, tenantId: string | null) {
  memoryAccessToken = token;
  memoryTenantId = tenantId;
  if (typeof window === "undefined") return;
  if (token) {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  }
  if (tenantId) {
    sessionStorage.setItem(TENANT_STORAGE_KEY, tenantId);
  } else {
    sessionStorage.removeItem(TENANT_STORAGE_KEY);
  }
}

export function getAccessToken(): string | null {
  if (memoryAccessToken) return memoryAccessToken;
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

export function getActiveTenantId(): string | null {
  if (memoryTenantId) return memoryTenantId;
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TENANT_STORAGE_KEY);
}

export function clearAuthCredentials() {
  setAuthCredentials(null, null);
}

export function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getAccessToken();
  const tenantId = getActiveTenantId();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (tenantId) {
    headers.set("X-Tenant-ID", tenantId);
  }

  return fetch(url, {
    credentials: "include",
    ...init,
    headers,
  });
}

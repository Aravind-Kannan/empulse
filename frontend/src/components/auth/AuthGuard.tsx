"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { GlobalPageLoader } from "@/components/ui/GlobalPageLoader";
import { useAuth } from "@/context/AuthContext";
import { onboardingPathForTenant } from "@/lib/auth";
import {
  isAuthPath,
  isOnboardingPath,
  isProtectedPath,
  isPublicPath,
  isWorkspaceSetupPath,
} from "@/lib/routes";

export { isPublicPath } from "@/lib/routes";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { authStatus, session, activeTenant } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const authError = searchParams.get("auth_error");

  const isLoading = authStatus === "loading";
  const isAuthenticated = authStatus === "authenticated";
  const protectedRoute = isProtectedPath(pathname);
  const needsWorkspaceSetup =
    isAuthenticated && activeTenant && !activeTenant.workspaceSetupComplete;

  useEffect(() => {
    if (isLoading) return;

    const authRoute = isAuthPath(pathname);
    const onboardingRoute = isOnboardingPath(pathname);
    const workspaceSetupRoute = isWorkspaceSetupPath(pathname);

    if (isAuthenticated && authRoute) {
      if (authError) return;
      router.replace(
        session?.onboarded
          ? "/dashboard"
          : onboardingPathForTenant(activeTenant),
      );
      return;
    }

    if (!isAuthenticated && protectedRoute) {
      router.replace("/login");
      return;
    }

    if (isAuthenticated && session?.onboarded && onboardingRoute) {
      router.replace("/dashboard");
      return;
    }

    if (needsWorkspaceSetup && !workspaceSetupRoute) {
      if (protectedRoute || onboardingRoute) {
        router.replace("/onboarding/workspace");
        return;
      }
    }

    if (
      isAuthenticated &&
      activeTenant?.workspaceSetupComplete &&
      workspaceSetupRoute
    ) {
      router.replace(session?.onboarded ? "/dashboard" : "/onboarding");
      return;
    }

    if (
      isAuthenticated &&
      !session?.onboarded &&
      protectedRoute &&
      !onboardingRoute
    ) {
      router.replace(onboardingPathForTenant(activeTenant));
    }
  }, [
    activeTenant,
    authError,
    authStatus,
    isLoading,
    isAuthenticated,
    needsWorkspaceSetup,
    pathname,
    protectedRoute,
    router,
    session?.onboarded,
  ]);

  if (isLoading && protectedRoute) {
    return <GlobalPageLoader label="Verifying session" />;
  }

  if (!isLoading && !isAuthenticated && protectedRoute) {
    return <GlobalPageLoader label="Redirecting to sign in" />;
  }

  return <>{children}</>;
}

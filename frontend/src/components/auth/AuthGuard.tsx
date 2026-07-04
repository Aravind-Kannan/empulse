"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { GlobalPageLoader } from "@/components/ui/GlobalPageLoader";
import { useAuth } from "@/context/AuthContext";
import {
  isAuthPath,
  isOnboardingPath,
  isProtectedPath,
  isPublicPath,
} from "@/lib/routes";

export { isPublicPath } from "@/lib/routes";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { authStatus, session } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isLoading = authStatus === "loading";
  const isAuthenticated = authStatus === "authenticated";
  const protectedRoute = isProtectedPath(pathname);

  useEffect(() => {
    if (isLoading) return;

    const publicRoute = isPublicPath(pathname);
    const authRoute = isAuthPath(pathname);
    const onboardingRoute = isOnboardingPath(pathname);

    if (isAuthenticated && authRoute) {
      router.replace(session?.onboarded ? "/dashboard" : "/onboarding");
      return;
    }

    if (!isAuthenticated && protectedRoute) {
      router.replace("/login");
      return;
    }

    if (isAuthenticated && onboardingRoute && session?.onboarded) {
      router.replace("/dashboard");
      return;
    }

    if (
      isAuthenticated &&
      !session?.onboarded &&
      protectedRoute &&
      !onboardingRoute
    ) {
      router.replace("/onboarding");
    }
  }, [
    authStatus,
    isLoading,
    isAuthenticated,
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

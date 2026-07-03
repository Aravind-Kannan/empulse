"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { GlobalPageLoader } from "@/components/ui/GlobalPageLoader";
import { useAuth } from "@/context/AuthContext";

const PUBLIC_PATHS = ["/", "/login", "/signup"];

function isPublicPath(pathname: string) {
  return PUBLIC_PATHS.includes(pathname);
}

function isAuthPath(pathname: string) {
  return pathname === "/login" || pathname === "/signup";
}

function isOnboardingPath(pathname: string) {
  return pathname.startsWith("/onboarding");
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { authStatus, session } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const isLoading = authStatus === "loading";
  const isAuthenticated = authStatus === "authenticated";

  useEffect(() => {
    if (isLoading) return;

    const publicRoute = isPublicPath(pathname);
    const authRoute = isAuthPath(pathname);
    const onboardingRoute = isOnboardingPath(pathname);

    if (isAuthenticated && authRoute) {
      router.replace(session?.onboarded ? "/dashboard" : "/onboarding");
      return;
    }

    if (!isAuthenticated && !publicRoute && !authRoute) {
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
      !onboardingRoute &&
      !publicRoute &&
      !authRoute
    ) {
      router.replace("/onboarding");
    }
  }, [authStatus, isLoading, isAuthenticated, pathname, router, session?.onboarded]);

  if (isLoading && !isAuthPath(pathname)) {
    return <GlobalPageLoader label="Verifying session" />;
  }

  if (
    !isAuthenticated &&
    !isPublicPath(pathname) &&
    !isAuthPath(pathname)
  ) {
    return <GlobalPageLoader label="Redirecting" />;
  }

  return <>{children}</>;
}

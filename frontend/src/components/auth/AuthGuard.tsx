"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/context/AuthContext";

const PUBLIC_PATHS = ["/"];

function isPublicPath(pathname: string) {
  return PUBLIC_PATHS.includes(pathname);
}

function isOnboardingPath(pathname: string) {
  return pathname.startsWith("/onboarding");
}

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, session } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    const publicRoute = isPublicPath(pathname);
    const onboardingRoute = isOnboardingPath(pathname);

    if (!isAuthenticated && !publicRoute) {
      router.replace("/");
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
      !publicRoute
    ) {
      router.replace("/onboarding");
    }
  }, [isAuthenticated, isLoading, pathname, router, session?.onboarded]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading session…
      </div>
    );
  }

  if (!isAuthenticated && !isPublicPath(pathname)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Redirecting…
      </div>
    );
  }

  return <>{children}</>;
}

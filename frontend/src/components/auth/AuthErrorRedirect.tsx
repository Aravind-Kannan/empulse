"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/**
 * Legacy OAuth errors land on `/` — forward to login with message preserved.
 */
export function AuthErrorRedirect() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const authError = searchParams.get("auth_error");
    if (!authError) return;
    router.replace(`/login?auth_error=${encodeURIComponent(authError)}`);
  }, [router, searchParams]);

  return null;
}

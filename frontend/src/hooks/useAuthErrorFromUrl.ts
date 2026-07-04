"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** Read `auth_error` from OAuth callback redirect, show once, then strip from URL. */
export function useAuthErrorFromUrl() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const authError = searchParams.get("auth_error");
    if (!authError) return;

    setError(authError);
    const params = new URLSearchParams(searchParams.toString());
    params.delete("auth_error");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  return error;
}

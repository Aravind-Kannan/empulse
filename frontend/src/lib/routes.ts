const PUBLIC_PATHS = ["/", "/login", "/signup"] as const;

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/era",
  "/kra",
  "/investigation",
  "/exit",
  "/settings",
  "/onboarding",
] as const;

export function isPublicPath(pathname: string) {
  return (PUBLIC_PATHS as readonly string[]).includes(pathname);
}

export function isAuthPath(pathname: string) {
  return pathname === "/login" || pathname === "/signup";
}

export function isOnboardingPath(pathname: string) {
  return pathname.startsWith("/onboarding");
}

export function isWorkspaceSetupPath(pathname: string) {
  return pathname === "/onboarding/workspace";
}

export function isProtectedPath(pathname: string) {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function isKnownAppPath(pathname: string) {
  return isPublicPath(pathname) || isProtectedPath(pathname);
}

/** Routes that render immediately — no session gate loader. */
export function isImmediateRoute(pathname: string) {
  return isPublicPath(pathname) || isAuthPath(pathname) || !isProtectedPath(pathname);
}

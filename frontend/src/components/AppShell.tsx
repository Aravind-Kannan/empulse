"use client";

import { usePathname } from "next/navigation";

import { Sidebar } from "@/components/Sidebar";
import {
  isAuthPath,
  isKnownAppPath,
  isOnboardingPath,
  isPublicPath,
} from "@/lib/routes";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isBareLayout =
    isPublicPath(pathname) ||
    isOnboardingPath(pathname) ||
    isAuthPath(pathname) ||
    !isKnownAppPath(pathname);

  if (isBareLayout) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden [--sidebar-width:17.75rem]">
      <Sidebar />
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

"use client";

import { usePathname } from "next/navigation";

import { Sidebar } from "@/components/Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isBareLayout =
    pathname === "/" ||
    pathname.startsWith("/onboarding") ||
    pathname === "/login" ||
    pathname === "/signup";

  if (isBareLayout) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

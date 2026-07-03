"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Network,
  Search,
  LogOut,
  Settings,
  BrainCircuit,
  Lock,
} from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  isWorkspaceUnlocked,
  workspaceRequiresIntegrations,
} from "@/lib/integrations";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/era", label: "Employee Risk Assessment", abbr: "ERA", icon: Users },
  { href: "/kra", label: "Knowledge Risk Assessment", abbr: "KRA", icon: Network },
  { href: "/investigation", label: "Incident Investigation", abbr: "II", icon: Search },
  { href: "/exit", label: "Employee Knowledge Handover", abbr: "EKH", icon: LogOut },
  { href: "/settings", label: "Settings", icon: Settings },
];

function integrationHint(path: string): string {
  const required = workspaceRequiresIntegrations(path);
  if (required.length === 0) return "";
  const names = required
    .map((id) => INTEGRATION_CATALOG.find((app) => app.id === id)?.name ?? id)
    .join(" or ");
  return `Connect ${names} in Settings → Integrations`;
}

export function Sidebar() {
  const pathname = usePathname();
  const { session, activeTenant, logout } = useAuth();
  const { config } = useIntegrations();

  const workspaceLabel = activeTenant
    ? `${activeTenant.companyName} Workspace`
    : session?.company
      ? `${session.company} Workspace`
      : "Workspace";

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-zinc-800 bg-slate-950">
      <div className="flex items-center gap-3 border-b border-zinc-800 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800 text-zinc-100">
          <BrainCircuit className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-zinc-100">Empulse</p>
          <p className="truncate text-xs text-zinc-500">{workspaceLabel}</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map(({ href, label, abbr, icon: Icon }) => {
          const isActive = pathname === href || pathname.startsWith(`${href}/`);
          const unlocked = isWorkspaceUnlocked(href, config);
          const hint = integrationHint(href);

          if (!unlocked) {
            return (
              <Link
                key={href}
                href="/settings/integrations"
                title={hint}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-900 hover:text-zinc-500"
              >
                <Lock className="h-4 w-4 shrink-0" />
                <span className="truncate">
                  {label}
                  {abbr && (
                    <span className="ml-1 text-xs text-zinc-700">({abbr})</span>
                  )}
                </span>
              </Link>
            );
          }

          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-zinc-800 text-zinc-50"
                  : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">
                {label}
                {abbr && (
                  <span className="ml-1 text-xs text-zinc-500">({abbr})</span>
                )}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-zinc-800 px-5 py-4">
        {session && (
          <div className="mb-3">
            <p className="truncate text-sm font-medium text-zinc-200">
              {session.name}
            </p>
            <p className="truncate text-xs text-zinc-500">{session.email}</p>
          </div>
        )}
        <button
          type="button"
          onClick={logout}
          className="mb-3 flex w-full items-center gap-2 rounded-lg border border-zinc-800 px-3 py-2 text-xs text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-200"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
        <p className="text-xs text-zinc-600">Powered by Cognee</p>
      </div>
    </aside>
  );
}

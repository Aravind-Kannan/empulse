"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Network,
  Search,
  LogOut,
  BrainCircuit,
  Lock,
  FileText,
  ChevronRight,
  Plug,
  GitBranch,
  Waypoints,
  type LucideIcon,
} from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { useIntegrations } from "@/context/IntegrationsContext";
import {
  INTEGRATION_CATALOG,
  isWorkspaceUnlocked,
  workspaceRequiresIntegrations,
} from "@/lib/integrations";

type NavItem = {
  href: string;
  label: string;
  abbr?: string;
  icon: LucideIcon;
};

type NavGroup = {
  title: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    title: "Overview",
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    title: "Intelligence",
    items: [
      { href: "/era", label: "Employee Risk Assessment", abbr: "ERA", icon: Users },
      { href: "/kra", label: "Knowledge Risk Assessment", abbr: "KRA", icon: Network },
      {
        href: "/investigation",
        label: "Incident Investigation",
        abbr: "II",
        icon: Search,
      },
      {
        href: "/exit",
        label: "Employee Knowledge Handover",
        abbr: "EKH",
        icon: FileText,
      },
    ],
  },
  {
    title: "Workspace",
    items: [
      { href: "/settings/integrations", label: "Integrations", icon: Plug },
      { href: "/settings/knowledge-graph-reset", label: "Knowledge graph reset", icon: Waypoints },
      { href: "/settings/org-chart", label: "Org Hub", icon: GitBranch },
    ],
  },
];

function isNavItemActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function integrationHint(path: string): string {
  const required = workspaceRequiresIntegrations(path);
  if (required.length === 0) return "";
  const names = required
    .map((id) => INTEGRATION_CATALOG.find((app) => app.id === id)?.name ?? id)
    .join(" or ");
  return `Connect ${names} in Integrations`;
}

function NavLink({
  item,
  isActive,
  unlocked,
  hint,
}: {
  item: NavItem;
  isActive: boolean;
  unlocked: boolean;
  hint: string;
}) {
  const Icon = item.icon;

  if (!unlocked) {
    return (
      <Link
        href="/settings/integrations"
        title={hint}
        className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-zinc-600 transition hover:bg-zinc-900/60 hover:text-zinc-500"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800/80 bg-zinc-950/50">
          <Lock className="h-4 w-4" />
        </span>
        <span className="min-w-0 truncate">
          {item.label}
          {item.abbr ? (
            <span className="ml-1 text-[10px] uppercase tracking-wide text-zinc-700">
              {item.abbr}
            </span>
          ) : null}
        </span>
      </Link>
    );
  }

  return (
    <Link
      href={item.href}
      className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
        isActive
          ? "bg-gradient-to-r from-violet-500/15 via-zinc-800/80 to-zinc-900/40 text-zinc-50 shadow-inner shadow-violet-950/20"
          : "text-zinc-400 hover:bg-zinc-900/70 hover:text-zinc-100"
      }`}
    >
      {isActive ? (
        <span className="absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full bg-gradient-to-b from-violet-400 to-sky-400" />
      ) : null}
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition ${
          isActive
            ? "border-violet-500/40 bg-violet-500/15 text-violet-200"
            : "border-zinc-800/80 bg-zinc-950/40 text-zinc-500 group-hover:border-zinc-700 group-hover:text-zinc-300"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 truncate">
        {item.label}
        {item.abbr ? (
          <span
            className={`ml-1.5 text-[10px] font-medium uppercase tracking-wider ${
              isActive ? "text-violet-300/80" : "text-zinc-600"
            }`}
          >
            {item.abbr}
          </span>
        ) : null}
      </span>
      {isActive ? (
        <ChevronRight className="h-4 w-4 shrink-0 text-violet-300/80" />
      ) : (
        <ChevronRight className="h-4 w-4 shrink-0 text-zinc-700 opacity-0 transition group-hover:opacity-100" />
      )}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { session, activeTenant, logout } = useAuth();
  const { config } = useIntegrations();

  const workspaceLabel = activeTenant
    ? activeTenant.companyName
    : session?.company ?? "Workspace";

  return (
    <aside className="relative flex h-full w-[17rem] shrink-0 flex-col border-r border-zinc-800/80 bg-slate-950/95 backdrop-blur-xl">
      <div
        className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-violet-500/20 to-transparent"
        aria-hidden
      />

      <div className="border-b border-zinc-800/80 px-4 py-5">
        <div className="flex items-center gap-3 rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-3 shadow-lg shadow-black/20">
          <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600/30 to-sky-600/20 ring-1 ring-violet-500/30">
            <BrainCircuit className="h-5 w-5 text-violet-200" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-zinc-50">
              Empulse
            </p>
            <p className="truncate text-[11px] uppercase tracking-wider text-zinc-500">
              {workspaceLabel}
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {navGroups.map((group) => (
          <div key={group.title}>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-600">
              {group.title}
            </p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const isActive = isNavItemActive(pathname, item.href);
                const unlocked = isWorkspaceUnlocked(item.href, config);
                return (
                  <NavLink
                    key={item.href}
                    item={item}
                    isActive={isActive}
                    unlocked={unlocked}
                    hint={integrationHint(item.href)}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-zinc-800/80 p-4">
        {session ? (
          <div className="mb-3 rounded-xl border border-zinc-800/80 bg-zinc-900/30 px-3 py-2.5">
            <p className="truncate text-sm font-medium text-zinc-200">
              {session.name}
            </p>
            <p className="truncate text-xs text-zinc-500">{session.email}</p>
          </div>
        ) : null}
        <button
          type="button"
          onClick={logout}
          className="mb-3 flex w-full items-center justify-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-zinc-400 transition hover:border-zinc-700 hover:bg-zinc-900 hover:text-zinc-200"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
        <p className="text-center text-[10px] tracking-wide text-zinc-600">
          Engineering intelligence
        </p>
      </div>
    </aside>
  );
}

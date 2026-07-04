"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
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
  ChevronUp,
  Plug,
  GitBranch,
  Building2,
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
      {
        href: "/era",
        label: "Employee Risk Assessment",
        icon: Users,
      },
      {
        href: "/kra",
        label: "Knowledge Risk Assessment",
        icon: Network,
      },
      {
        href: "/investigation",
        label: "Incident Investigation",
        icon: Search,
      },
      {
        href: "/exit",
        label: "Employee Knowledge Handover",
        icon: FileText,
      },
    ],
  },
  {
    title: "Workspace",
    items: [
      { href: "/settings/integrations", label: "Integrations", icon: Plug },
      { href: "/settings/knowledge-graph-reset", label: "Knowledge graph reset", icon: Waypoints },
      {
        href: "/settings/org-chart",
        label: "Organization Hub",
        icon: GitBranch,
      },
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

function initialsFromName(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function SidebarUserMenu({
  name,
  email,
  onLogout,
}: {
  name: string;
  email: string;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      {open ? (
        <div
          className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border border-zinc-800/90 bg-zinc-950/95 p-1 shadow-xl shadow-black/40 ring-1 ring-white/5 backdrop-blur-xl"
          role="menu"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onLogout();
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm text-zinc-300 transition hover:bg-zinc-900 hover:text-zinc-50"
          >
            <LogOut className="h-4 w-4 shrink-0 text-zinc-500" />
            Sign out
          </button>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="menu"
        className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${
          open
            ? "border-zinc-700/80 bg-zinc-900/80"
            : "border-zinc-800/80 bg-zinc-900/40 hover:border-zinc-700/80 hover:bg-zinc-900/60"
        }`}
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-violet-600/35 to-sky-600/25 text-xs font-semibold text-violet-100 ring-1 ring-violet-500/25">
          {initialsFromName(name)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-zinc-200">
            {name}
          </span>
          <span className="block truncate text-[11px] text-zinc-500">{email}</span>
        </span>
        <ChevronUp
          className={`h-4 w-4 shrink-0 text-zinc-500 transition ${open ? "rotate-180" : ""}`}
        />
      </button>
    </div>
  );
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
        className="group flex items-center gap-3 rounded-xl px-3 py-2 text-zinc-600 transition hover:bg-zinc-900/60 hover:text-zinc-500"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-zinc-800/80 bg-zinc-950/50">
          <Lock className="h-4 w-4" />
        </span>
        <span className="min-w-0 text-xs leading-snug">{item.label}</span>
      </Link>
    );
  }

  return (
    <Link
      href={item.href}
      className={`group relative flex items-center gap-3 rounded-xl px-3 py-2 transition ${
        isActive
          ? "bg-gradient-to-r from-violet-500/15 via-zinc-800/80 to-zinc-900/40 text-zinc-50 shadow-inner shadow-violet-950/20"
          : "text-zinc-400 hover:bg-zinc-900/70 hover:text-zinc-100"
      }`}
    >
      {isActive ? (
        <span className="absolute left-0 top-1/2 h-7 w-1 -translate-y-1/2 rounded-r-full bg-gradient-to-b from-violet-400 to-sky-400" />
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
      <span className="min-w-0 flex-1 text-xs leading-snug">{item.label}</span>
      {isActive ? (
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-violet-300/80" />
      ) : (
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-zinc-700 opacity-0 transition group-hover:opacity-100" />
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
    <aside className="relative flex h-full w-[17.75rem] shrink-0 flex-col border-r border-zinc-800/80 bg-slate-950/95 backdrop-blur-xl">
      <div
        className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-violet-500/20 to-transparent"
        aria-hidden
      />

      <div className="shrink-0 px-4 pb-4 pt-5">
        <Link href="/dashboard" className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600/35 to-sky-600/20 ring-1 ring-violet-500/30">
            <BrainCircuit className="h-[18px] w-[18px] text-violet-100" />
          </div>
          <div className="min-w-0">
            <p className="text-[15px] font-semibold tracking-tight text-zinc-50">
              Empulse
            </p>
            <p className="text-[11px] text-zinc-500">Engineering intelligence</p>
          </div>
        </Link>

        <div className="mt-4 flex items-center gap-2.5 rounded-xl border border-zinc-800/70 bg-zinc-900/30 px-3 py-2.5">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-zinc-950/70 ring-1 ring-zinc-800/80">
            <Building2 className="h-3.5 w-3.5 text-zinc-500" />
          </span>
          <div className="min-w-0">
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-zinc-600">
              Workspace
            </p>
            <p className="truncate text-sm font-medium text-zinc-200">
              {workspaceLabel}
            </p>
          </div>
        </div>
      </div>

      <div className="mx-4 h-px shrink-0 bg-zinc-800/80" />

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {navGroups.map((group) => (
          <div key={group.title}>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-600">
              {group.title}
            </p>
            <div className="space-y-0.5">
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

      <div className="shrink-0 border-t border-zinc-800/80 p-3">
        {session ? (
          <SidebarUserMenu
            name={session.name}
            email={session.email}
            onLogout={logout}
          />
        ) : null}
      </div>
    </aside>
  );
}

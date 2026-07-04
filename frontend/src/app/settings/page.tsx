"use client";

import Link from "next/link";
import { ChevronRight, Settings2, Users, Bell, GitBranch } from "lucide-react";

import { TenantSwitcher } from "@/components/settings/TenantSwitcher";

const organizationSections = [
  {
    href: "/settings/identity-mapping",
    title: "Identity Mapping",
    description:
      "Map GitHub handles, Jira emails, Slack IDs, and Notion users to employee records.",
    icon: Users,
  },
];

const workspaceSections = [
  {
    href: "/settings/era-alerts",
    title: "ERA Alerts",
    description:
      "Team-channel Slack webhooks, review cadence, and alert thresholds.",
    icon: Bell,
  },
];

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-8">
      <header>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900">
            <Settings2 className="h-5 w-5 text-zinc-400" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">Settings</h1>
            <p className="text-sm text-zinc-500">
              Workspace preferences, identity reconciliation, and alerts.
            </p>
          </div>
        </div>
      </header>

      <TenantSwitcher />

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/20 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-600">
          Quick access
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            href="/settings/integrations"
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-700 hover:text-zinc-100"
          >
            Integrations
            <ChevronRight className="h-4 w-4 text-zinc-600" />
          </Link>
          <Link
            href="/settings/org-chart"
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-700 hover:text-zinc-100"
          >
            <GitBranch className="h-4 w-4 text-zinc-500" />
            Org Chart
            <ChevronRight className="h-4 w-4 text-zinc-600" />
          </Link>
        </div>
      </section>

      <section className="space-y-3">
        <p className="px-1 text-xs font-semibold uppercase tracking-[0.16em] text-zinc-600">
          Organization
        </p>
        {organizationSections.map(({ href, title, description, icon: Icon }) => (
          <SettingsLinkCard
            key={href}
            href={href}
            title={title}
            description={description}
            icon={Icon}
          />
        ))}
      </section>

      <section className="space-y-3">
        <p className="px-1 text-xs font-semibold uppercase tracking-[0.16em] text-zinc-600">
          Alerts &amp; workspace
        </p>
        {workspaceSections.map(({ href, title, description, icon: Icon }) => (
          <SettingsLinkCard
            key={href}
            href={href}
            title={title}
            description={description}
            icon={Icon}
          />
        ))}
      </section>
    </div>
  );
}

function SettingsLinkCard({
  href,
  title,
  description,
  icon: Icon,
}: {
  href: string;
  title: string;
  description: string;
  icon: typeof Users;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 transition hover:border-zinc-700 hover:bg-zinc-900/70"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
        <Icon className="h-5 w-5 text-zinc-300" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-zinc-100">{title}</p>
        <p className="text-sm text-zinc-500">{description}</p>
      </div>
      <ChevronRight className="h-5 w-5 shrink-0 text-zinc-600" />
    </Link>
  );
}

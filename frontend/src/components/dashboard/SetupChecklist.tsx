"use client";

import Link from "next/link";
import { CheckCircle2, Circle, Plug } from "lucide-react";

import { useIntegrations } from "@/context/IntegrationsContext";
import {
  getConnectedIntegrationIds,
  getConnectedMemberImportSources,
  INTEGRATION_CATALOG,
  isIntegrationConnected,
  MEMBER_IMPORT_SOURCES,
  type IntegrationId,
} from "@/lib/integrations";

const SETUP_ITEMS: {
  id: string;
  label: string;
  description: string;
  href: string;
  isComplete: (connected: IntegrationId[]) => boolean;
  requiredAny?: IntegrationId[];
}[] = [
  {
    id: "people",
    label: "Member roster connected",
    description: "Slack, Notion, Jira, or GitHub — imports flat member list",
    href: "/settings/integrations",
    requiredAny: [...MEMBER_IMPORT_SOURCES],
    isComplete: (connected) =>
      MEMBER_IMPORT_SOURCES.some((id) => connected.includes(id)),
  },
  {
    id: "github",
    label: "GitHub connected",
    description: "Code ownership graph for KRA / SPOF detection",
    href: "/settings/integrations",
    isComplete: (connected) => connected.includes("github"),
  },
  {
    id: "jira",
    label: "Jira connected",
    description: "Incident and sprint data for investigation workspace",
    href: "/settings/integrations",
    isComplete: (connected) => connected.includes("jira"),
  },
  {
    id: "notion-docs",
    label: "Notion docs connected",
    description: "Runbooks and wikis for knowledge risk coverage",
    href: "/settings/integrations",
    isComplete: (connected) => connected.includes("notion"),
  },
];

export function SetupChecklist() {
  const { config } = useIntegrations();
  const connected = getConnectedIntegrationIds(config);
  const memberSources = getConnectedMemberImportSources(config);

  const incomplete = SETUP_ITEMS.filter((item) => !item.isComplete(connected));
  if (incomplete.length === 0) return null;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
            <Plug className="h-5 w-5 text-zinc-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
              Data source checklist
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              Empulse workspaces need live integrations.{" "}
              {memberSources.length > 0
                ? `Members importing from ${memberSources.join(", ")}.`
                : "Connect any integration to import your member roster."}
            </p>
          </div>
        </div>
        <Link
          href="/settings/integrations"
          className="shrink-0 text-sm text-sky-400 hover:text-sky-300"
        >
          Manage →
        </Link>
      </div>

      <ul className="space-y-2">
        {SETUP_ITEMS.map((item) => {
          const done = item.isComplete(connected);
          return (
            <li key={item.id}>
              <Link
                href={item.href}
                className={`flex items-start gap-3 rounded-lg border px-4 py-3 transition ${
                  done
                    ? "border-emerald-500/20 bg-emerald-500/5"
                    : "border-zinc-800 bg-zinc-950/50 hover:border-zinc-700"
                }`}
              >
                {done ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                ) : (
                  <Circle className="mt-0.5 h-4 w-4 shrink-0 text-zinc-600" />
                )}
                <div>
                  <p
                    className={`text-sm font-medium ${done ? "text-emerald-300" : "text-zinc-200"}`}
                  >
                    {item.label}
                  </p>
                  <p className="text-xs text-zinc-500">{item.description}</p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 text-xs text-zinc-600">
        {INTEGRATION_CATALOG.filter((app) =>
          isIntegrationConnected(app.id, config),
        ).length}{" "}
        of {INTEGRATION_CATALOG.length} integrations connected
      </p>
    </section>
  );
}

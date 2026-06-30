"use client";

import Link from "next/link";
import { ChevronRight, Network, Plug, Settings2 } from "lucide-react";

const settingsSections = [
  {
    href: "/settings/integrations",
    title: "Integrations",
    description:
      "Connect Slack, Notion, GitHub, and Jira. Trigger global Cognee graph sync.",
    icon: Plug,
  },
  {
    href: "/settings/graph-debugger",
    title: "Graph Debugger",
    description:
      "Run the Notion → Ollama → Cognee simulation and inspect extracted graph triples.",
    icon: Network,
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
              Workspace configuration and connected services.
            </p>
          </div>
        </div>
      </header>

      <section className="space-y-3">
        {settingsSections.map(({ href, title, description, icon: Icon }) => (
          <Link
            key={href}
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
        ))}
      </section>
    </div>
  );
}

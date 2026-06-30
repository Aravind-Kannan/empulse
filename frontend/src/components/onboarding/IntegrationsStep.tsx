"use client";

import { MessageSquare, NotebookPen } from "lucide-react";

import { useOnboarding } from "@/context/OnboardingContext";

export function IntegrationsStep() {
  const { integrations, updateIntegrations, setStep } = useOnboarding();

  return (
    <div className="mx-auto w-full max-w-lg space-y-8">
      <div className="text-center">
        <h2 className="text-2xl font-semibold text-zinc-100">
          Connect your tools
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          Optional integrations stored locally for this session.
        </p>
      </div>

      <div className="space-y-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800">
              <MessageSquare className="h-4 w-4 text-zinc-300" />
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-100">Slack</p>
              <p className="text-xs text-zinc-500">Bot token for incident threads</p>
            </div>
          </div>
          <input
            type="password"
            value={integrations.slackBotToken}
            onChange={(e) =>
              updateIntegrations({ slackBotToken: e.target.value })
            }
            placeholder="xoxb-..."
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-800">
              <NotebookPen className="h-4 w-4 text-zinc-300" />
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-100">Notion</p>
              <p className="text-xs text-zinc-500">API key for runbooks & docs</p>
            </div>
          </div>
          <input
            type="password"
            value={integrations.notionApiKey}
            onChange={(e) => updateIntegrations({ notionApiKey: e.target.value })}
            placeholder="secret_..."
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => setStep(1)}
          className="flex-1 rounded-lg border border-zinc-700 px-4 py-2.5 text-sm text-zinc-300 transition hover:bg-zinc-900"
        >
          Back
        </button>
        <button
          type="button"
          onClick={() => setStep(3)}
          className="flex-1 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white"
        >
          Continue to Org Chart
        </button>
      </div>
    </div>
  );
}

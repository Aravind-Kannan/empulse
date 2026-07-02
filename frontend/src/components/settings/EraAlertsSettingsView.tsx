"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell, ChevronLeft, Loader2 } from "lucide-react";

import { fetchEraSettings, updateEraSettings } from "@/lib/api";
import type { EraSettings } from "@/lib/types";

export function EraAlertsSettingsView() {
  const [settings, setSettings] = useState<EraSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchEraSettings()
      .then(setSettings)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load ERA settings"),
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updated = await updateEraSettings(settings);
      setSettings(updated);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save ERA settings");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-zinc-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading ERA alert settings…
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
        {error ?? "ERA settings unavailable."}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link
          href="/settings"
          className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-300"
        >
          <ChevronLeft className="h-4 w-4" />
          Settings
        </Link>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900">
            <Bell className="h-5 w-5 text-violet-300" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-zinc-100">ERA Alerts</h1>
            <p className="text-sm text-zinc-500">
              Team-channel notifications for continuity risk signals — never individual DMs.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={(event) => void handleSave(event)} className="space-y-5">
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
          <h2 className="text-sm font-medium text-zinc-200">Slack webhook (optional)</h2>
          <p className="mt-1 text-xs text-zinc-500">
            Post summaries to a shared channel such as #eng-leadership. Disabled in demo mode.
          </p>
          <label className="mt-4 flex items-center gap-2 text-sm text-zinc-300">
            <input
              type="checkbox"
              checked={settings.slack_webhook_enabled}
              onChange={(event) =>
                setSettings({ ...settings, slack_webhook_enabled: event.target.checked })
              }
              className="rounded border-zinc-600"
            />
            Enable Slack webhook for tier-1 SPOF alerts
          </label>
          <input
            type="url"
            value={settings.slack_webhook_url}
            onChange={(event) =>
              setSettings({ ...settings, slack_webhook_url: event.target.value })
            }
            placeholder="https://hooks.slack.com/services/..."
            className="mt-3 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
          />
        </section>

        <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
          <h2 className="text-sm font-medium text-zinc-200">Alert thresholds</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm text-zinc-400">
              Unmapped identity threshold
              <input
                type="number"
                min={1}
                value={settings.unmapped_threshold}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    unmapped_threshold: Number(event.target.value),
                  })
                }
                className="mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </label>
            <label className="block text-sm text-zinc-400">
              Review cadence (days)
              <input
                type="number"
                min={1}
                value={settings.review_cadence_days}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    review_cadence_days: Number(event.target.value),
                  })
                }
                className="mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-zinc-500"
              />
            </label>
          </div>
        </section>

        {error ? (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            {error}
          </div>
        ) : null}
        {saved ? (
          <p className="text-sm text-emerald-300">ERA alert settings saved.</p>
        ) : null}

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save settings"}
        </button>
      </form>
    </div>
  );
}

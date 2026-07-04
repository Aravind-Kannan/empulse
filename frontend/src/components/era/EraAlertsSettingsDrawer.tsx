"use client";

import { createPortal } from "react-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bell, Loader2, X } from "lucide-react";

import { fetchEraSettings, updateEraSettings } from "@/lib/api";
import type { EraSettings } from "@/lib/types";

interface EraAlertsSettingsDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function EraAlertsSettingsDrawer({ open, onClose }: EraAlertsSettingsDrawerProps) {
  const [settings, setSettings] = useState<EraSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const handleClose = useCallback(() => {
    setVisible(false);
    window.setTimeout(onClose, 200);
  }, [onClose]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    setSaved(false);
    fetchEraSettings()
      .then(setSettings)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load ERA settings"),
      )
      .finally(() => setLoading(false));

    const frame = window.requestAnimationFrame(() => setVisible(true));
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        handleClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, handleClose]);

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

  if (!mounted || !open) return null;

  const content = (
    <>
      <button
        type="button"
        aria-label="Close alert settings"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={handleClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Configure ERA alerts"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl transition-transform duration-200 ease-out ${
          visible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900">
              <Bell className="h-4 w-4 text-violet-300" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-zinc-500">ERA</p>
              <h2 className="text-lg font-semibold text-zinc-100">Configure alerts</h2>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={handleClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          {loading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-zinc-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading alert settings…
            </div>
          ) : !settings ? (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
              {error ?? "ERA settings unavailable."}
            </div>
          ) : (
            <form onSubmit={(event) => void handleSave(event)} className="space-y-5">
              <p className="text-xs leading-relaxed text-zinc-500">
                Team-channel notifications for continuity risk signals — never individual DMs.
              </p>

              <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <h3 className="text-sm font-medium text-zinc-200">Slack webhook (optional)</h3>
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

              <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                <h3 className="text-sm font-medium text-zinc-200">Alert thresholds</h3>
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
                className="w-full rounded-lg bg-zinc-100 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-white disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save settings"}
              </button>
            </form>
          )}
        </div>
      </aside>
    </>
  );

  return createPortal(content, document.body);
}

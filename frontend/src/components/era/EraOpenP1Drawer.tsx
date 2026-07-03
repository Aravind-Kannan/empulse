"use client";

import Link from "next/link";
import { createPortal } from "react-dom";
import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2, X } from "lucide-react";

import { fetchEraOpenP1Issues } from "@/lib/api";
import { formatLocalDate } from "@/lib/datetime";
import type { EraOpenP1IssuesResponse } from "@/lib/types";

interface EraOpenP1DrawerProps {
  open: boolean;
  onClose: () => void;
}

function priorityClass(priority: string) {
  if (priority === "Critical") {
    return "border-red-500/40 bg-red-500/10 text-red-200";
  }
  if (priority === "Highest" || priority === "High") {
    return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  }
  return "border-zinc-600 bg-zinc-800/50 text-zinc-300";
}

function formatUpdatedAt(iso: string | null | undefined) {
  return formatLocalDate(iso, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function EraOpenP1Drawer({ open, onClose }: EraOpenP1DrawerProps) {
  const [data, setData] = useState<EraOpenP1IssuesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const response = await fetchEraOpenP1Issues();
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load open P1 issues.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleClose = useCallback(() => {
    setVisible(false);
    window.setTimeout(onClose, 200);
  }, [onClose]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    void load();
    const frame = window.requestAnimationFrame(() => setVisible(true));
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, load]);

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

  if (!mounted || !open) return null;

  const content = (
    <>
      <button
        type="button"
        aria-label="Close open P1 issues"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={handleClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Open P1 Jira issues"
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl transition-transform duration-200 ease-out ${
          visible ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">ERA</p>
            <h2 className="text-lg font-semibold text-zinc-100">Open P1 issues</h2>
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
              Loading Jira issues…
            </div>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          ) : null}

          {!loading && data && !data.jira_synced ? (
            <div className="space-y-3 py-4 text-sm text-zinc-400">
              <p>Jira has not been synced yet.</p>
              <Link
                href="/settings/integrations"
                className="inline-flex text-violet-300 hover:text-violet-200"
              >
                Connect and sync Jira →
              </Link>
            </div>
          ) : null}

          {!loading && data?.jira_synced && data.issues.length === 0 ? (
            <p className="py-8 text-center text-sm text-zinc-500">
              No open Critical, Highest, or High priority issues in the latest sync.
            </p>
          ) : null}

          {!loading && data?.jira_synced && data.issues.length > 0 ? (
            <div className="space-y-3">
              <p className="text-xs text-zinc-500">{data.filters_note}</p>
              {data.issues.map((issue) => (
                <article
                  key={issue.issue_key}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-zinc-400">
                          {issue.issue_key}
                        </span>
                        <span
                          className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${priorityClass(issue.priority)}`}
                        >
                          {issue.priority}
                        </span>
                        <span className="text-[10px] uppercase text-zinc-500">
                          {issue.status}
                        </span>
                      </div>
                      <p className="mt-2 text-sm font-medium text-zinc-100">
                        {issue.summary || "—"}
                      </p>
                    </div>
                    {issue.issue_url ? (
                      <a
                        href={issue.issue_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                        title="Open in Jira"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    ) : null}
                  </div>
                  <dl className="mt-3 grid gap-1 text-xs text-zinc-500">
                    <div className="flex gap-2">
                      <dt className="shrink-0">Assignee</dt>
                      <dd className="text-zinc-300">
                        {issue.assignee_name ??
                          (issue.assignee_unmapped
                            ? "Unmapped"
                            : "Unassigned")}
                      </dd>
                    </div>
                    {issue.component_name ? (
                      <div className="flex gap-2">
                        <dt className="shrink-0">Component</dt>
                        <dd className="text-zinc-300">{issue.component_name}</dd>
                      </div>
                    ) : null}
                    <div className="flex gap-2">
                      <dt className="shrink-0">Updated</dt>
                      <dd>{formatUpdatedAt(issue.updated_at)}</dd>
                    </div>
                  </dl>
                  {issue.assignee_unmapped ? (
                    <Link
                      href="/settings/identity-mapping"
                      className="mt-2 inline-block text-xs text-amber-300 hover:text-amber-200"
                    >
                      Map assignee in identity settings
                    </Link>
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );

  return createPortal(content, document.body);
}

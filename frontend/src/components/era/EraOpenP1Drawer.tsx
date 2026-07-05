"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { fetchEraOpenP1Issues } from "@/lib/api";
import { formatLocalDate } from "@/lib/datetime";
import type { EraOpenP1IssuesResponse } from "@/lib/types";

import { EraSidePanel } from "./EraSidePanel";
import { getInitials } from "./era-utils";

interface EraOpenP1DrawerProps {
  open: boolean;
  onClose: () => void;
}

function priorityBadgeClass(priority: string): string {
  if (priority === "Critical") {
    return "border-red-500/30 bg-red-500/15 text-red-200";
  }
  if (priority === "Highest" || priority === "High") {
    return "border-amber-500/30 bg-amber-500/15 text-amber-200";
  }
  return "border-zinc-600/40 bg-zinc-500/15 text-zinc-300";
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

  if (!mounted) return null;

  return (
    <EraSidePanel
      open={open}
      visible={visible}
      onClose={handleClose}
      eyebrow="Operational signals"
      title="Open P1 issues"
      subtitle={
        data?.jira_synced
          ? `${data.issues.length} issue${data.issues.length === 1 ? "" : "s"} from Jira`
          : "Critical, highest, and high priority"
      }
      ariaLabel="Open P1 Jira issues"
      closeButtonRef={closeButtonRef}
    >
      {loading ? (
        <div className="flex items-center gap-2 py-8 text-[11px] text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading Jira issues…
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[11px] text-red-300">
          {error}
        </div>
      ) : null}

      {!loading && data && !data.jira_synced ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-6 text-center">
          <p className="text-[11px] text-zinc-400">Jira has not been synced yet.</p>
          <Link
            href="/settings/integrations"
            className="mt-2 inline-flex text-[11px] text-violet-300 hover:text-violet-200"
          >
            Connect and sync Jira →
          </Link>
        </div>
      ) : null}

      {!loading && data?.jira_synced && data.issues.length === 0 ? (
        <p className="py-8 text-center text-[11px] text-zinc-500">
          No open Critical, Highest, or High priority issues in the latest sync.
        </p>
      ) : null}

      {!loading && data?.jira_synced && data.issues.length > 0 ? (
        <div className="space-y-3">
          {data.filters_note ? (
            <p className="text-[10px] text-zinc-600">{data.filters_note}</p>
          ) : null}
          <ul className="space-y-1.5">
            {data.issues.map((issue) => {
              const assigneeLabel =
                issue.assignee_name ??
                (issue.assignee_unmapped ? "Unmapped" : "Unassigned");

              return (
                <li
                  key={issue.issue_key}
                  className="flex items-start justify-between gap-2 rounded border border-zinc-800/60 bg-zinc-950/30 px-2.5 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="shrink-0 font-mono text-[11px] text-zinc-400">
                        {issue.issue_key}
                      </span>
                      <span
                        className={`shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-medium uppercase ${priorityBadgeClass(issue.priority)}`}
                      >
                        {issue.priority}
                      </span>
                      <span className="shrink-0 text-[9px] uppercase text-zinc-600">
                        {issue.status}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] leading-snug text-zinc-200">
                      {issue.summary || "—"}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[9px] text-zinc-500">
                      <span
                        className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 ${
                          issue.assignee_unmapped
                            ? "border-amber-500/25 bg-amber-500/5 text-amber-300"
                            : "border-zinc-700/80 bg-zinc-900/60 text-zinc-400"
                        }`}
                      >
                        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-zinc-800 text-[8px] font-medium text-zinc-300">
                          {getInitials(assigneeLabel)}
                        </span>
                        <span className="max-w-[6rem] truncate">{assigneeLabel}</span>
                      </span>
                      {issue.component_name ? (
                        <>
                          <span>·</span>
                          <span className="truncate text-zinc-400">
                            {issue.component_name}
                          </span>
                        </>
                      ) : null}
                      <span>·</span>
                      <span>{formatUpdatedAt(issue.updated_at)}</span>
                    </div>
                    {issue.assignee_unmapped ? (
                      <Link
                        href="/settings/org-chart?tab=identity"
                        className="mt-1.5 inline-block text-[10px] text-amber-300 hover:text-amber-200"
                      >
                        Map assignee →
                      </Link>
                    ) : null}
                  </div>
                  {issue.issue_url ? (
                    <a
                      href={issue.issue_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-0.5 shrink-0 text-zinc-500 hover:text-sky-300"
                      aria-label={`Open ${issue.issue_key} in Jira`}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </EraSidePanel>
  );
}

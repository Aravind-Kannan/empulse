"use client";

import { useMemo } from "react";
import { X } from "lucide-react";

import {
  formatKraComponentLabel,
  parseGitHubComponentDisplay,
} from "@/lib/github-component-display";
import type { KraAnalyticsResponse, KraNode } from "@/lib/types";

interface KraComponentDrawerProps {
  component: KraNode;
  graph: KraAnalyticsResponse;
  onClose: () => void;
}

export function KraComponentDrawer({
  component,
  graph,
  onClose,
}: KraComponentDrawerProps) {
  const linkedEngineerIds = useMemo(
    () =>
      new Set(
        graph.links
          .filter((link) => link.target === component.id)
          .map((link) => link.source),
      ),
    [graph.links, component.id],
  );

  const linkedEngineers = graph.nodes.filter(
    (node) => node.type === "engineer" && linkedEngineerIds.has(node.id),
  );

  const ownershipByEngineerId = useMemo(() => {
    const shares = new Map<string, number>();
    for (const link of graph.links) {
      if (link.target === component.id && link.codebase_share_pct != null) {
        shares.set(link.source, link.codebase_share_pct);
      }
    }
    return shares;
  }, [graph.links, component.id]);

  const ownershipSource = useMemo(() => {
    const link = graph.links.find(
      (entry) =>
        entry.target === component.id && entry.ownership_source != null,
    );
    return link?.ownership_source ?? null;
  }, [graph.links, component.id]);

  const githubDisplay = parseGitHubComponentDisplay(
    component.description,
    component.label,
  );
  const componentTitle = formatKraComponentLabel(component);
  const spofHeadline = component.github_verified_spof
    ? "GitHub-verified Single Point of Failure"
    : "Single Point of Failure";
  const spofReasons = component.spof_reasons ?? [];

  return (
    <>
      <button
        type="button"
        aria-label="Close drawer"
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-800 bg-slate-950 shadow-2xl transition-transform duration-300 ease-out`}
      >
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">
              {githubDisplay ? "GitHub component" : "System component"}
            </p>
            {githubDisplay ? (
              <div className="mt-1">
                <p className="text-sm font-medium text-zinc-400">
                  {githubDisplay.repo}
                </p>
                <h2 className="text-lg font-semibold tracking-tight text-zinc-100">
                  {githubDisplay.folder}
                </h2>
              </div>
            ) : (
              <h2 className="text-lg font-semibold text-zinc-100">
                {componentTitle}
              </h2>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          {component.is_spof && (
            <div className="rounded-lg border border-orange-500/40 bg-orange-500/10 px-4 py-3 text-sm text-orange-200">
              <p className="font-medium text-orange-100">{spofHeadline}</p>
              {spofReasons.length > 0 ? (
                <ul className="mt-2 space-y-2">
                  {spofReasons.map((reason) => (
                    <li key={reason.kind}>
                      <span className="font-medium text-orange-100">
                        {reason.title}
                      </span>
                      <span className="text-orange-200/90"> — {reason.detail}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-orange-200/90">
                  Knowledge is concentrated on too few engineers for this
                  component.
                </p>
              )}
              {component.bus_factor != null && (
                <p className="mt-2 text-xs text-orange-300/80">
                  Bus factor: {component.bus_factor}
                </p>
              )}
            </div>
          )}

          <section>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">
              Description
            </h3>
            <p className="text-sm leading-relaxed text-zinc-400">
              {githubDisplay ? (
                <>
                  GitHub path{" "}
                  <span className="font-mono text-zinc-300">
                    {githubDisplay.repo}/{githubDisplay.folder}/
                  </span>
                </>
              ) : (
                component.description || "No description available."
              )}
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium text-zinc-200">
              Documentation
            </h3>
            <ul className="space-y-2">
              {(component.documentation_sources ?? []).map((source) => (
                <li
                  key={source}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-300"
                >
                  {source}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-zinc-200">Current owners</h3>
              {ownershipSource && (
                <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
                  {ownershipSource === "github" ? "GitHub telemetry" : "Org chart"}
                </span>
              )}
            </div>
            <ul className="space-y-1 text-sm text-zinc-400">
              {linkedEngineers.map((engineer) => {
                const sharePct = ownershipByEngineerId.get(engineer.id);
                return (
                  <li key={engineer.id}>
                    {engineer.label}
                    {sharePct != null ? ` — ${sharePct.toFixed(1)}%` : ""}
                    {engineer.role ? ` (${engineer.role})` : ""}
                  </li>
                );
              })}
            </ul>
            {linkedEngineers.length === 0 && (
              <p className="text-sm text-zinc-500">No owners linked yet.</p>
            )}
            {ownershipSource === "github" && (
              <p className="mt-2 text-xs text-zinc-500">
                Percentages from recent GitHub change volume on this path — not
                org-chart assignments.
              </p>
            )}
          </section>
        </div>
      </aside>
    </>
  );
}

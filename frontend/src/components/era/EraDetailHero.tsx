"use client";

import Link from "next/link";
import { AlertTriangle, Check, Minus } from "lucide-react";

import type {
  EraEmployeeMetrics,
  EraIdentityMapping,
  IdentityCoverageLevel,
  IntegrationId,
} from "@/lib/types";

import { getInitials } from "./era-utils";

interface EraDetailHeroProps {
  employee: EraEmployeeMetrics;
  identityMappings?: Partial<Record<IntegrationId, EraIdentityMapping>>;
}

const PROVIDERS: IntegrationId[] = ["github", "jira", "slack", "notion"];

const PROVIDER_LABELS: Record<IntegrationId, string> = {
  github: "GH",
  jira: "Jira",
  slack: "Slack",
  notion: "Notion",
};

function coverageDot(level: IdentityCoverageLevel | undefined): string {
  if (level === "confirmed" || level === "high") return "bg-emerald-400";
  if (level === "medium") return "bg-amber-400";
  return "bg-zinc-600";
}

function riskTextClass(level: EraEmployeeMetrics["risk_level"]): string {
  if (level === "high") return "text-red-300";
  if (level === "medium") return "text-amber-300";
  return "text-emerald-300";
}

function isProviderMapped(mapping?: EraIdentityMapping): boolean {
  if (!mapping) return false;
  if (mapping.level === "missing") return false;
  return (
    Boolean(mapping.display_label?.trim()) ||
    mapping.level === "confirmed" ||
    mapping.level === "high"
  );
}

function IdentityMappingChip({
  provider,
  mapping,
}: {
  provider: IntegrationId;
  mapping?: EraIdentityMapping;
}) {
  const level = mapping?.level ?? "missing";
  const label = mapping?.display_label?.trim();
  const mapped = Boolean(label);
  const displayText = mapped ? label : level === "missing" ? "—" : level;
  const tooltipText = mapped
    ? `${PROVIDER_LABELS[provider]}: ${label}`
    : `${PROVIDER_LABELS[provider]}: not mapped`;

  return (
    <span
      tabIndex={0}
      className={`group/identity relative inline-flex max-w-[8.5rem] items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] outline-none focus-visible:ring-1 focus-visible:ring-violet-500 ${
        mapped
          ? "border-zinc-700 bg-zinc-950/50 text-zinc-300"
          : "border-dashed border-zinc-800 text-zinc-600"
      }`}
    >
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-0 z-20 mb-1.5 hidden max-w-[14rem] rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-[10px] leading-snug text-zinc-200 shadow-lg group-hover/identity:block group-focus-within/identity:block"
      >
        {tooltipText}
      </span>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${coverageDot(level)}`} />
      <span className="font-medium text-zinc-400">{PROVIDER_LABELS[provider]}</span>
      <span className="truncate">{displayText}</span>
      {mapped ? (
        <Check className="h-2.5 w-2.5 shrink-0 text-emerald-500/80" />
      ) : (
        <Minus className="h-2.5 w-2.5 shrink-0 text-zinc-600" />
      )}
    </span>
  );
}

export function EraDetailHero({
  employee,
  identityMappings = {},
}: EraDetailHeroProps) {
  const score = Math.round(employee.risk_factor_score);
  const recovery = employee.recovery_estimate_weeks;
  const allIdentitiesMapped = PROVIDERS.every((provider) =>
    isProviderMapped(identityMappings[provider]),
  );

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex gap-3">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-base font-semibold text-violet-200">
          {getInitials(employee.name)}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <h2 className="text-lg font-semibold text-zinc-100">{employee.name}</h2>
            <span className="text-sm text-zinc-400">{employee.role}</span>
          </div>
          <p className="mt-0.5 truncate text-xs text-zinc-500">
            {employee.email}
            <span className="mx-1.5 text-zinc-700">·</span>
            <span className="font-mono">{employee.employee_id}</span>
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase ${
                employee.risk_level === "high"
                  ? "border-red-500/30 bg-red-500/10 text-red-300"
                  : employee.risk_level === "medium"
                    ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                    : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
              }`}
            >
              {employee.risk_level === "high" && <AlertTriangle className="h-3 w-3" />}
              {employee.risk_level}
            </span>
            {employee.departure_watchlist && (
              <span className="rounded-full border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-medium text-rose-300">
                Watchlist
              </span>
            )}
            {employee.identity_warning && (
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-200">
                Fuzzy identity
              </span>
            )}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <p className={`text-3xl font-bold tabular-nums leading-none ${riskTextClass(employee.risk_level)}`}>
            {score}%
          </p>
          <p className="mt-0.5 text-[9px] font-medium uppercase tracking-wide text-zinc-500">
            Continuity risk
          </p>
          {recovery && (
            <p className="mt-1.5 text-[10px] font-medium text-amber-300/90">
              {recovery.min}–{recovery.max} wk recovery
            </p>
          )}
        </div>
      </div>

      <div className="mt-3 border-t border-zinc-800/80 pt-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1.5">
            {PROVIDERS.map((provider) => (
              <IdentityMappingChip
                key={provider}
                provider={provider}
                mapping={identityMappings[provider]}
              />
            ))}
          </div>
          {!allIdentitiesMapped && (
            <Link
              href="/settings/org-chart?tab=identity"
              className="shrink-0 text-[10px] text-violet-300 hover:text-violet-200"
            >
              Fix mapping
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

"use client";

import { Check, CircleDashed, Fingerprint, Loader2 } from "lucide-react";

import { IntegrationLogo } from "@/components/integrations/IntegrationLogos";
import { INTEGRATION_CATALOG, type IntegrationId } from "@/lib/integrations";

export type MemberImportStepStatus = "pending" | "active" | "done" | "error";

export interface MemberImportStep {
  id: IntegrationId | "hierarchy" | "identity";
  status: MemberImportStepStatus;
  detail?: string;
}

function stepLabel(id: MemberImportStep["id"]): string {
  if (id === "hierarchy") return "Organizing org hierarchy";
  if (id === "identity") return "Auto-mapping identities";
  return INTEGRATION_CATALOG.find((app) => app.id === id)?.name ?? id;
}

function stepAccent(id: MemberImportStep["id"]): string {
  if (id === "hierarchy") return "bg-violet-500/15 text-violet-200";
  if (id === "identity") return "bg-sky-500/15 text-sky-200";
  const app = INTEGRATION_CATALOG.find((entry) => entry.id === id);
  return app ? `${app.accentBg} ${app.iconClassName}` : "bg-zinc-800 text-zinc-300";
}

export function MemberImportProgress({
  steps,
  title = "Importing your organization",
  subtitle,
}: {
  steps: MemberImportStep[];
  title?: string;
  subtitle?: string;
}) {
  const active = steps.some((step) => step.status === "active");

  return (
    <div
      className="mx-auto w-full max-w-md space-y-6"
      aria-live="polite"
      aria-busy={active}
    >
      <div className="text-center">
        <p className="text-lg font-medium text-zinc-200">{title}</p>
        {subtitle ? (
          <p className="mt-1 text-sm text-zinc-500">{subtitle}</p>
        ) : null}
      </div>

      <ol className="space-y-2 rounded-2xl border border-zinc-800/80 bg-zinc-950/40 p-4">
        {steps.map((step) => {
          const label = stepLabel(step.id);
          const isIntegration =
            step.id !== "hierarchy" && step.id !== "identity";

          return (
            <li
              key={step.id}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 transition ${
                step.status === "active"
                  ? "border-sky-500/30 bg-sky-500/5"
                  : step.status === "done"
                    ? "border-emerald-500/20 bg-emerald-500/5"
                    : step.status === "error"
                      ? "border-red-500/30 bg-red-500/5"
                      : "border-transparent bg-zinc-900/30"
              }`}
            >
              <span
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${stepAccent(step.id)}`}
              >
                {isIntegration ? (
                  <IntegrationLogo
                    id={step.id as IntegrationId}
                    className="h-5 w-5"
                  />
                ) : step.id === "identity" ? (
                  <Fingerprint className="h-4 w-4" />
                ) : (
                  <CircleDashed className="h-4 w-4" />
                )}
              </span>

              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-medium ${
                    step.status === "active"
                      ? "text-zinc-100"
                      : step.status === "done"
                        ? "text-zinc-400"
                        : step.status === "error"
                          ? "text-red-200"
                          : "text-zinc-500"
                  }`}
                >
                  {label}
                </p>
                {step.detail ? (
                  <p className="truncate text-xs text-zinc-500">{step.detail}</p>
                ) : null}
              </div>

              <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                {step.status === "done" ? (
                  <Check className="h-4 w-4 text-emerald-400" aria-hidden />
                ) : step.status === "active" ? (
                  <Loader2
                    className="h-4 w-4 animate-spin text-sky-400"
                    aria-hidden
                  />
                ) : step.status === "error" ? (
                  <span className="text-xs text-red-400" aria-hidden>
                    !
                  </span>
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-zinc-600" aria-hidden />
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

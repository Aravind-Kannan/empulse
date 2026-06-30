"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";

import { useAuth } from "@/context/AuthContext";
import { useOnboarding } from "@/context/OnboardingContext";
import { ingestOrgChart } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";

import { OrgChartTree } from "./OrgChartTree";

export function OrgChartStep() {
  const router = useRouter();
  const { completeOnboarding } = useAuth();
  const { signUp, orgChart, setStep } = useOnboarding();
  const { refreshMetrics } = useWorkspace();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleIngest() {
    setIsSubmitting(true);
    setError(null);

    const payload = {
      ...orgChart,
      company: signUp.company || orgChart.company,
    };

    try {
      await ingestOrgChart(payload);
      await refreshMetrics();
      completeOnboarding();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-semibold text-zinc-100">
          Org Chart Setup
        </h2>
        <p className="mt-2 text-sm text-zinc-400">
          Review your team hierarchy and component ownership before ingesting
          into Cognee.
        </p>
      </div>

      <OrgChartTree />

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => setStep(2)}
          disabled={isSubmitting}
          className="rounded-lg border border-zinc-700 px-4 py-2.5 text-sm text-zinc-300 transition hover:bg-zinc-900 disabled:opacity-50"
        >
          Back
        </button>
        <button
          type="button"
          onClick={handleIngest}
          disabled={isSubmitting}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Ingesting to Cognee…
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Confirm &amp; Ingest to Cognee
            </>
          )}
        </button>
      </div>
    </div>
  );
}

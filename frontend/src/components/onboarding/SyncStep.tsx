"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";

import { OnboardingShell } from "@/components/onboarding/OnboardingShell";
import { useAuth } from "@/context/AuthContext";

/** Legacy route — redirects to dashboard without blocking on sync. */
export function SyncStep() {
  const router = useRouter();
  const { completeOnboarding } = useAuth();
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFinish() {
    setFinishing(true);
    setError(null);
    try {
      await completeOnboarding();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete setup");
      setFinishing(false);
    }
  }

  return (
    <OnboardingShell currentStep={2} wide>
      <div className="mx-auto max-w-lg text-center">
        <h1 className="text-2xl font-semibold text-zinc-100">You&apos;re all set</h1>
        <p className="mt-2 text-sm text-zinc-400">
          Data sync runs from your dashboard when you choose — never blocks
          navigation. ERA, KRA, and Investigation unlock automatically when
          ingestion completes.
        </p>

        {error && (
          <div className="mt-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={() => void handleFinish()}
          disabled={finishing}
          className="mt-8 inline-flex items-center justify-center gap-2 rounded-lg bg-zinc-100 px-6 py-2.5 text-sm font-medium text-slate-950 transition hover:bg-white disabled:opacity-50"
        >
          {finishing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Opening dashboard…
            </>
          ) : (
            <>
              Go to dashboard
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </OnboardingShell>
  );
}
